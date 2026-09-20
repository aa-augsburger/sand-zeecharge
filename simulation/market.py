from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from models.validation import finite


def generate_hourly_prices(
    start: datetime | None = None,
    days: int = 30,
    seed: int = 42,
) -> pd.DataFrame:
    """Synthetic hourly prices: low at night, peak in evening, with bounded noise."""
    if not isinstance(days, int) or isinstance(days, bool) or days <= 0:
        raise ValueError("Le nombre de jours doit être un entier positif")
    if start is None:
        start = datetime(2026, 1, 1, 0, 0, 0)

    rng = np.random.default_rng(seed)
    hours = days * 24
    timestamps = pd.date_range(start=start, periods=hours, freq="h")

    base_by_hour = np.array(
        [
            0.06, 0.05, 0.05, 0.05, 0.05, 0.06,
            0.08, 0.10, 0.12, 0.11, 0.10, 0.09,
            0.09, 0.10, 0.11, 0.13, 0.16, 0.22,
            0.28, 0.30, 0.25, 0.18, 0.12, 0.08,
        ]
    )
    hour_of_day = timestamps.hour.to_numpy()
    base = base_by_hour[hour_of_day]
    noise = rng.normal(0, 0.01, size=hours)
    prices = np.clip(base + noise, 0.03, 0.40)

    return pd.DataFrame({"timestamp": timestamps, "price_chf_kwh": prices})


def load_prices(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"timestamp", "price_chf_kwh"}
    if not required.issubset(df.columns):
        raise ValueError(f"CSV must contain columns: {required}")
    return df


def save_prices(df: pd.DataFrame, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


class EnergyMarket:
    def __init__(self, prices: pd.DataFrame, duration_h: float | None = None) -> None:
        if not {"timestamp", "price_chf_kwh"}.issubset(prices.columns):
            raise ValueError("Colonnes requises : timestamp, price_chf_kwh")
        if prices.empty:
            raise ValueError("Le marché ne contient aucun prix")
        frame = prices.copy().reset_index(drop=True)
        try:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
            frame["price_chf_kwh"] = pd.to_numeric(frame["price_chf_kwh"], errors="raise")
        except (ValueError, TypeError) as exc:
            raise ValueError("Dates ou prix invalides dans le marché") from exc
        dates = frame["timestamp"]
        if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
            raise ValueError("Les dates doivent être valides, uniques et croissantes")
        for value in frame["price_chf_kwh"]:
            finite("prix", float(value))  # Negative prices are valid market observations.
        if duration_h is not None:
            finite("durée du pas", duration_h, positive=True)
        if len(frame) > 1:
            intervals = dates.diff().iloc[1:]
            if not (intervals == intervals.iloc[0]).all():
                raise ValueError("Cadence irrégulière : données manquantes ou intervalles différents")
            inferred = intervals.iloc[0].total_seconds() / 3600
            if duration_h is not None and not np.isclose(inferred, duration_h, rtol=0, atol=1e-9):
                raise ValueError("La durée demandée ne correspond pas aux horodatages")
            duration_h = inferred
        self.duration_h = 1.0 if duration_h is None else duration_h
        finite("durée du pas", self.duration_h, positive=True)
        self.prices = frame

    @classmethod
    def from_csv(cls, path: Path | str) -> "EnergyMarket":
        return cls(load_prices(path))

    @classmethod
    def generate_and_save(
        cls,
        path: Path | str,
        days: int = 30,
        seed: int = 42,
        start: datetime | None = None,
    ) -> "EnergyMarket":
        df = generate_hourly_prices(start=start, days=days, seed=seed)
        save_prices(df, path)
        return cls(df)

    def __len__(self) -> int:
        return len(self.prices)

    def price_at(self, index: int) -> tuple[pd.Timestamp, float]:
        row = self.prices.iloc[index]
        return row["timestamp"], float(row["price_chf_kwh"])
