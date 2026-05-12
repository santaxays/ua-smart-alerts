import pandas as pd

from .base import Alert, Detector

DROP_THRESHOLD = 0.40   # 40% decline in ROAS vs baseline


class RoasDropDetector(Detector):
    name = "roas_drop"
    severity = "warning"
    description = "ROAS D1 dropped >40% vs the 7-day baseline"

    def check(self, df: pd.DataFrame) -> list[Alert]:
        now = df["timestamp"].max()
        cutoff_24h = now - pd.Timedelta(hours=24)
        cutoff_7d  = now - pd.Timedelta(days=7)

        def roas_per_campaign(window: pd.DataFrame) -> pd.Series:
            agg = window.groupby("campaign").agg(
                revenue=("revenue_d1", "sum"),
                cost=("cost", "sum"),
            )
            agg["roas"] = agg["revenue"] / agg["cost"].replace(0, float("nan"))
            return agg["roas"]

        last24   = df[df["timestamp"] > cutoff_24h]
        baseline = df[df["timestamp"] <= cutoff_7d]

        roas_now  = roas_per_campaign(last24)
        roas_base = roas_per_campaign(baseline)

        alerts = []
        for campaign in roas_now.index:
            if campaign not in roas_base.index:
                continue

            r_now  = roas_now[campaign]
            r_base = roas_base[campaign]

            if pd.isna(r_now) or pd.isna(r_base) or r_base == 0:
                continue

            drop = (r_base - r_now) / r_base
            if drop > DROP_THRESHOLD:
                alerts.append(Alert(
                    detector_name=self.name,
                    campaign=campaign,
                    severity=self.severity,
                    title=f"Падение ROAS D1 — {campaign}",
                    body=(
                        f"ROAS D1 упал с {r_base:.1%} (7-дневная база) "
                        f"до {r_now:.1%} за последние 24 часа "
                        f"(снижение {drop:.0%})."
                    ),
                    metric_value=round(r_now, 4),
                    baseline_value=round(r_base, 4),
                ))

        return alerts
