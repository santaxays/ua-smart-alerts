"""Unit tests for each detector using minimal inline DataFrames."""
import pandas as pd
import pytest

from src.detectors.cpi_spike import CpiSpikeDetector
from src.detectors.budget_overrun import BudgetOverrunDetector
from src.detectors.roas_drop import RoasDropDetector
from src.detectors.zero_impressions import ZeroImpressionsDetector

NOW = pd.Timestamp("2026-05-11 12:00:00")


def make_ts(hours_ago: float) -> pd.Timestamp:
    return NOW - pd.Timedelta(hours=hours_ago)


# ── CpiSpikeDetector ──────────────────────────────────────────────────────────

class TestCpiSpikeDetector:
    detector = CpiSpikeDetector()

    def _base_row(self, hours_ago, cost, installs, campaign="TestCamp"):
        return {
            "timestamp": make_ts(hours_ago),
            "campaign": campaign,
            "cost": cost,
            "installs": installs,
            "impressions": 10000,
            "clicks": 300,
            "revenue_d1": cost * 0.5,
            "retention_d1": 0.35,
            "daily_budget": 5000,
            "country": "US",
            "ad_network": "meta",
        }

    def _df(self, rows):
        return pd.DataFrame(rows)

    def test_spike_triggers(self):
        # prior 6h: CPI = $2.00 ($200 / 100 installs)
        # last 6h: CPI = $3.50 ($175 / 50 installs) → +75%
        rows = [self._base_row(h, cost=200, installs=100) for h in range(7, 13)]
        rows += [self._base_row(h, cost=175, installs=50) for h in range(1, 7)]
        alerts = self.detector.check(self._df(rows))
        assert len(alerts) == 1
        assert alerts[0].campaign == "TestCamp"
        assert alerts[0].severity == "warning"

    def test_no_spike_below_threshold(self):
        # +10% CPI — should not trigger
        rows = [self._base_row(h, cost=200, installs=100) for h in range(7, 13)]
        rows += [self._base_row(h, cost=200, installs=91) for h in range(1, 7)]
        alerts = self.detector.check(self._df(rows))
        assert alerts == []

    def test_low_spend_suppressed(self):
        # Large CPI spike but last 6h spend is only $30 (< MIN_SPEND $100)
        rows = [self._base_row(h, cost=200, installs=100) for h in range(7, 13)]
        rows += [self._base_row(h, cost=5, installs=1) for h in range(1, 7)]
        alerts = self.detector.check(self._df(rows))
        assert alerts == []


# ── BudgetOverrunDetector ─────────────────────────────────────────────────────

class TestBudgetOverrunDetector:
    detector = BudgetOverrunDetector()

    def _row(self, hours_ago, cost, budget=1000, campaign="TestCamp"):
        return {
            "timestamp": make_ts(hours_ago),
            "campaign": campaign,
            "cost": cost,
            "daily_budget": budget,
            "installs": 50, "clicks": 200, "impressions": 8000,
            "revenue_d1": cost * 0.5, "retention_d1": 0.35,
            "country": "US", "ad_network": "meta",
        }

    def test_overrun_triggers(self):
        # Budget $1000, today spend = $1300 → 1.3× > 1.2 threshold
        rows = [self._row(h, cost=130) for h in range(0, 10)]
        alerts = self.detector.check(pd.DataFrame(rows))
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_within_budget_no_alert(self):
        # Budget $1000, today spend = $500 → no alert
        rows = [self._row(h, cost=50) for h in range(0, 10)]
        alerts = self.detector.check(pd.DataFrame(rows))
        assert alerts == []

    def test_exactly_at_threshold_no_alert(self):
        # Exactly 1.2× should NOT trigger (condition is strictly greater than)
        rows = [self._row(h, cost=100) for h in range(0, 12)]  # $1200 = 1.2×
        alerts = self.detector.check(pd.DataFrame(rows))
        assert alerts == []


# ── RoasDropDetector ──────────────────────────────────────────────────────────

class TestRoasDropDetector:
    detector = RoasDropDetector()

    def _row(self, hours_ago, cost, revenue, campaign="TestCamp"):
        return {
            "timestamp": make_ts(hours_ago),
            "campaign": campaign,
            "cost": cost,
            "revenue_d1": revenue,
            "daily_budget": 5000,
            "installs": 50, "clicks": 200, "impressions": 8000,
            "retention_d1": 0.35, "country": "US", "ad_network": "meta",
        }

    def test_roas_drop_triggers(self):
        # Baseline ROAS ~55%, last 24h ROAS ~28% → drop ~49%
        base_rows = [self._row(h, cost=100, revenue=55) for h in range(200, 400)]
        recent    = [self._row(h, cost=100, revenue=28) for h in range(1, 24)]
        alerts = self.detector.check(pd.DataFrame(base_rows + recent))
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"

    def test_small_roas_drop_no_alert(self):
        # Only 10% drop — should not trigger
        base_rows = [self._row(h, cost=100, revenue=55) for h in range(200, 400)]
        recent    = [self._row(h, cost=100, revenue=50) for h in range(1, 24)]
        alerts = self.detector.check(pd.DataFrame(base_rows + recent))
        assert alerts == []


# ── ZeroImpressionsDetector ───────────────────────────────────────────────────

class TestZeroImpressionsDetector:
    detector = ZeroImpressionsDetector()

    def _row(self, hours_ago, impressions, cost=50, campaign="TestCamp"):
        return {
            "timestamp": make_ts(hours_ago),
            "campaign": campaign,
            "impressions": impressions,
            "cost": cost,
            "daily_budget": 5000,
            "installs": max(impressions // 200, 0),
            "clicks": max(impressions // 40, 0),
            "revenue_d1": cost * 0.5,
            "retention_d1": 0.35,
            "country": "US", "ad_network": "meta",
        }

    def test_zero_impressions_triggers(self):
        # Had spend in last 24h, but last 2 rows have zero impressions
        rows = [self._row(h, impressions=10000) for h in range(3, 24)]
        rows += [self._row(h, impressions=0, cost=0) for h in [1, 0]]
        alerts = self.detector.check(pd.DataFrame(rows))
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_healthy_impressions_no_alert(self):
        rows = [self._row(h, impressions=10000) for h in range(0, 24)]
        alerts = self.detector.check(pd.DataFrame(rows))
        assert alerts == []

    def test_no_prior_spend_no_alert(self):
        # Zero impressions AND zero spend — campaign was never running today
        rows = [self._row(h, impressions=0, cost=0) for h in range(0, 5)]
        alerts = self.detector.check(pd.DataFrame(rows))
        assert alerts == []
