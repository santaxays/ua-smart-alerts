import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

import claude_enrich
from alert_builder import build_slack_blocks
from data_loader import load_recent_data
from deduplicator import StateStore
from detectors.cpi_spike import CpiSpikeDetector
from detectors.budget_overrun import BudgetOverrunDetector
from detectors.roas_drop import RoasDropDetector
from detectors.zero_impressions import ZeroImpressionsDetector
from slack_client import SlackClient

DATA_PATH = Path("data/sample_hourly_data.csv")

# To add a 5th detector: create src/detectors/my_check.py, subclass Detector,
# then add MyCheckDetector to this list. Nothing else changes.
DETECTORS = [
    CpiSpikeDetector(),
    BudgetOverrunDetector(),
    RoasDropDetector(),
    ZeroImpressionsDetector(),
]


def run() -> int:
    load_dotenv()

    slack_token = os.getenv("SLACK_BOT_TOKEN")
    channel_id  = os.getenv("SLACK_CHANNEL_ID")

    if not slack_token or not channel_id:
        print(
            "ERROR: SLACK_BOT_TOKEN and SLACK_CHANNEL_ID must be set in .env",
            file=sys.stderr,
        )
        return 1

    try:
        # Load 8 days so ROAS detector has a 7-day baseline plus the last 24h
        df = load_recent_data(DATA_PATH, hours_back=8 * 24)
    except FileNotFoundError:
        print(f"ERROR: data file not found at {DATA_PATH}", file=sys.stderr)
        return 1

    store  = StateStore()
    slack  = SlackClient(slack_token)

    alerts_to_send = []
    suppressed     = 0

    for detector in DETECTORS:
        try:
            triggered = detector.check(df)
        except Exception as exc:
            print(f"ERROR in {detector.name}: {exc}", file=sys.stderr)
            continue

        for alert in triggered:
            if store.should_send(alert):
                alerts_to_send.append(alert)
            else:
                suppressed += 1
                print(f"[SUPPRESSED] {alert.dedup_key}")

    enrichments = claude_enrich.enrich_alerts(alerts_to_send)

    sent   = 0
    failed = 0

    for alert in alerts_to_send:
        enrichment = enrichments.get(alert.dedup_key)
        payload, fallback = build_slack_blocks(alert, enrichment)

        try:
            slack.send_attachment(channel_id, payload, fallback)
            store.record_sent(alert)
            sent += 1
            print(f"[SENT] {alert.dedup_key}")
        except RuntimeError as err:
            failed += 1
            print(f"[FAILED] {alert.dedup_key}: {err}")

    if sent == 0 and suppressed == 0 and failed == 0:
        print("Всё в норме — аномалий не обнаружено.")

    print(f"\nОтправлено: {sent}, подавлено: {suppressed}, ошибок: {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
