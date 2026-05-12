import json
from datetime import datetime, date
from pathlib import Path

from detectors.base import Alert

STATE_PATH = Path("data/alert_state.json")
RESEND_AFTER_HOURS = 4


class StateStore:
    def __init__(self, path: Path = STATE_PATH):
        self.path = path
        self._state: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, indent=2, default=str))

    def should_send(self, alert: Alert) -> bool:
        key = alert.dedup_key
        if key not in self._state:
            return True

        entry = self._state[key]
        last_seen = datetime.fromisoformat(entry["last_seen"])

        # Re-raise if it's a new calendar day vs when we last sent
        if last_seen.date() < date.today():
            return True

        # Re-raise if the alert has been quiet long enough to be "stale"
        hours_since = (datetime.now() - last_seen).total_seconds() / 3600
        if hours_since >= RESEND_AFTER_HOURS:
            return True

        return False

    def record_sent(self, alert: Alert) -> None:
        key = alert.dedup_key
        now_str = datetime.now().isoformat()

        if key in self._state:
            self._state[key]["last_seen"] = now_str
            self._state[key]["count"] += 1
        else:
            self._state[key] = {
                "first_seen": now_str,
                "last_seen":  now_str,
                "count":      1,
            }

        self._save()
