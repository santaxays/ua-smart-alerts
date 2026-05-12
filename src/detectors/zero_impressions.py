import pandas as pd

from .base import Alert, Detector


class ZeroImpressionsDetector(Detector):
    name = "zero_impressions"
    severity = "critical"
    description = "Campaign had spend in last 24h but zero impressions for 2+ hours"

    def check(self, df: pd.DataFrame) -> list[Alert]:
        now = df["timestamp"].max()
        cutoff_24h = now - pd.Timedelta(hours=24)
        cutoff_2h  = now - pd.Timedelta(hours=2)

        # Only consider campaigns that were actively spending in the last 24h
        active = (
            df[df["timestamp"] > cutoff_24h]
            .groupby("campaign")["cost"]
            .sum()
        )
        active_campaigns = active[active > 0].index

        last2h = df[df["timestamp"] > cutoff_2h]

        alerts = []
        for campaign in active_campaigns:
            camp_last2 = last2h[last2h["campaign"] == campaign]

            # Need 2+ hourly rows with zero impressions (not just data absence)
            if len(camp_last2) < 2:
                continue

            if camp_last2["impressions"].sum() == 0:
                spend_24h = active[campaign]
                alerts.append(Alert(
                    detector_name=self.name,
                    campaign=campaign,
                    severity=self.severity,
                    title=f"Нет показов — {campaign}",
                    body=(
                        f"Кампания потратила ${spend_24h:.0f} за последние 24 часа, "
                        f"но последние {len(camp_last2)} часа — ноль показов. "
                        f"Возможна техническая проблема."
                    ),
                    metric_value=0.0,
                    baseline_value=float(spend_24h),
                ))

        return alerts
