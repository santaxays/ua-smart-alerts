import pandas as pd

from .base import Alert, Detector

OVERRUN_RATIO = 1.2   # trigger when spend > budget × 1.2


class BudgetOverrunDetector(Detector):
    name = "budget_overrun"
    severity = "critical"
    description = "Daily spend exceeded the daily budget by more than 20%"

    def check(self, df: pd.DataFrame) -> list[Alert]:
        today = df["timestamp"].max().date()
        today_df = df[df["timestamp"].dt.date == today]

        agg = today_df.groupby("campaign").agg(
            total_spend=("cost", "sum"),
            daily_budget=("daily_budget", "first"),
        )

        alerts = []
        for campaign, row in agg.iterrows():
            limit = row["daily_budget"] * OVERRUN_RATIO
            if row["total_spend"] > limit:
                alerts.append(Alert(
                    detector_name=self.name,
                    campaign=campaign,
                    severity=self.severity,
                    title=f"Превышение бюджета — {campaign}",
                    body=(
                        f"Дневной расход ${row['total_spend']:.0f} "
                        f"превысил бюджет ${row['daily_budget']:.0f} "
                        f"в {row['total_spend']/row['daily_budget']:.1f}× раз."
                    ),
                    metric_value=round(row["total_spend"], 2),
                    baseline_value=float(row["daily_budget"]),
                ))

        return alerts
