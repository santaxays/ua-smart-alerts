import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

from data_loader import load_recent_data
from deduplicator import StateStore
from detectors.cpi_spike import CpiSpikeDetector
from detectors.budget_overrun import BudgetOverrunDetector
from detectors.roas_drop import RoasDropDetector
from detectors.zero_impressions import ZeroImpressionsDetector

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

    try:
        # Load 8 days so ROAS detector has a 7-day baseline plus the last 24h
        df = load_recent_data(DATA_PATH, hours_back=8 * 24)
    except FileNotFoundError:
        print(f"ERROR: data file not found at {DATA_PATH}", file=sys.stderr)
        return 1

    store = StateStore()
    alerts_fired = []

    for detector in DETECTORS:
        try:
            triggered = detector.check(df)
        except Exception as exc:
            print(f"ERROR in {detector.name}: {exc}", file=sys.stderr)
            continue

        for alert in triggered:
            if store.should_send(alert):
                alerts_fired.append(alert)
                store.record_sent(alert)
                print(f"[{alert.severity.upper()}] {alert.title}")
                print(f"  {alert.body}")
                print(f"  metric={alert.metric_value}  baseline={alert.baseline_value}")
                print(f"  dedup_key={alert.dedup_key}")
                print()
            else:
                print(f"[SUPPRESSED] {alert.dedup_key}")

    if not alerts_fired:
        print("Всё в норме — аномалий не обнаружено.")

    return 0


if __name__ == "__main__":
    sys.exit(run())
