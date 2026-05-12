"""Tests for StateStore deduplication logic."""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.detectors.base import Alert
from src.deduplicator import StateStore, RESEND_AFTER_HOURS


def make_alert(campaign="TestCamp") -> Alert:
    return Alert(
        detector_name="test_detector",
        campaign=campaign,
        severity="warning",
        title="Test alert",
        body="Something is wrong.",
        metric_value=3.5,
        baseline_value=2.0,
    )


@pytest.fixture
def store(tmp_path):
    return StateStore(path=tmp_path / "alert_state.json")


def test_first_call_returns_true(store):
    alert = make_alert()
    assert store.should_send(alert) is True


def test_second_call_within_4h_returns_false(store):
    alert = make_alert()
    store.record_sent(alert)
    assert store.should_send(alert) is False


def test_call_after_4h_returns_true(store, tmp_path):
    alert = make_alert()
    state_path = tmp_path / "alert_state.json"

    # Manually write a state entry with last_seen 5 hours ago
    old_time = (datetime.now() - timedelta(hours=RESEND_AFTER_HOURS + 1)).isoformat()
    state = {alert.dedup_key: {"first_seen": old_time, "last_seen": old_time, "count": 1}}
    state_path.write_text(json.dumps(state))

    fresh_store = StateStore(path=state_path)
    assert fresh_store.should_send(alert) is True


def test_different_campaigns_are_independent(store):
    alert_a = make_alert(campaign="CampA")
    alert_b = make_alert(campaign="CampB")

    store.record_sent(alert_a)

    assert store.should_send(alert_a) is False
    assert store.should_send(alert_b) is True


def test_record_sent_increments_count(store, tmp_path):
    state_path = tmp_path / "alert_state.json"
    s = StateStore(path=state_path)
    alert = make_alert()

    s.record_sent(alert)
    s.record_sent(alert)
    s.record_sent(alert)

    state = json.loads(state_path.read_text())
    assert state[alert.dedup_key]["count"] == 3
