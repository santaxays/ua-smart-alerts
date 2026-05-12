from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass
class Alert:
    detector_name: str
    campaign: str
    severity: str          # "critical" | "warning" | "info"
    title: str
    body: str
    metric_value: float
    baseline_value: float

    @property
    def dedup_key(self) -> str:
        return f"{self.detector_name}:{self.campaign}:{date.today()}"


class Detector(ABC):
    name: str = ""
    severity: str = "warning"
    description: str = ""

    @abstractmethod
    def check(self, df: pd.DataFrame) -> list[Alert]:
        """Analyse df and return any triggered alerts."""
        ...
