import pandas as pd

from .base import Alert, Detector

SPIKE_THRESHOLD = 0.25   # 25% rise in CPI
MIN_SPEND = 100.0        # ignore campaigns with tiny recent spend


class CpiSpikeDetector(Detector):
    name = "cpi_spike"
    severity = "warning"
    description = "CPI rose >25% in the last 6 hours vs the prior 6 hours"

    def check(self, df: pd.DataFrame) -> list[Alert]:
        now = df["timestamp"].max()
        cutoff_6h  = now - pd.Timedelta(hours=6)
        cutoff_12h = now - pd.Timedelta(hours=12)

        last6  = df[df["timestamp"] > cutoff_6h]
        prior6 = df[(df["timestamp"] > cutoff_12h) & (df["timestamp"] <= cutoff_6h)]

        def window_cpi(window: pd.DataFrame) -> pd.Series:
            agg = window.groupby("campaign").agg(
                cost=("cost", "sum"),
                installs=("installs", "sum"),
            )
            agg["cpi"] = agg["cost"] / agg["installs"].replace(0, float("nan"))
            return agg

        last6_stats  = window_cpi(last6)
        prior6_stats = window_cpi(prior6)

        alerts = []
        for campaign in last6_stats.index:
            if campaign not in prior6_stats.index:
                continue

            cpi_now  = last6_stats.loc[campaign, "cpi"]
            cpi_prev = prior6_stats.loc[campaign, "cpi"]
            spend    = last6_stats.loc[campaign, "cost"]

            if pd.isna(cpi_now) or pd.isna(cpi_prev) or cpi_prev == 0:
                continue
            if spend < MIN_SPEND:
                continue

            change = (cpi_now - cpi_prev) / cpi_prev
            if change > SPIKE_THRESHOLD:
                alerts.append(Alert(
                    detector_name=self.name,
                    campaign=campaign,
                    severity=self.severity,
                    title=f"Скачок CPI — {campaign}",
                    body=(
                        f"CPI вырос с ${cpi_prev:.2f} до ${cpi_now:.2f} "
                        f"(+{change:.0%}) за последние 6 часов. "
                        f"Расход за период: ${spend:.0f}."
                    ),
                    metric_value=round(cpi_now, 4),
                    baseline_value=round(cpi_prev, 4),
                ))

        return alerts
