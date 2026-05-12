from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_recent_data(path: str | Path, hours_back: int = 24) -> pd.DataFrame:
    """Load CSV and return rows from the last `hours_back` hours.

    Uses the most recent timestamp in the CSV as "now" so planted anomalies
    fire correctly regardless of when you run the script.
    """
    df = pd.read_csv(path, parse_dates=["timestamp"])

    now = df["timestamp"].max()
    cutoff = now - pd.Timedelta(hours=hours_back)

    return df[df["timestamp"] > cutoff].copy().reset_index(drop=True)
