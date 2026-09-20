import pandas as pd
import pytest

from simulation.market import EnergyMarket, generate_hourly_prices


@pytest.mark.parametrize("timestamps,prices", [
    ([], []),
    (["2026-01-01", "2026-01-01"], [.05, .06]),
    (["2026-01-02", "2026-01-01"], [.05, .06]),
    (["2026-01-01 00:00", "2026-01-01 01:00", "2026-01-01 03:00"], [.05, .06, .07]),
    (["invalid"], [.05]),
    ([None], [.05]),
    (["2026-01-01"], [float("nan")]),
    (["2026-01-01"], [float("inf")]),
    (["2026-01-01"], ["oops"]),
])
def test_rejects_invalid_market_data(timestamps, prices):
    with pytest.raises(ValueError):
        EnergyMarket(pd.DataFrame({"timestamp": timestamps, "price_chf_kwh": prices}))


def test_csv_missing_columns_and_empty_file(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text("wrong,price_chf_kwh\n2026-01-01,0.05\n")
    with pytest.raises(ValueError, match="columns"):
        EnergyMarket.from_csv(path)
    path.write_text("timestamp,price_chf_kwh\n")
    with pytest.raises(ValueError, match="aucun"):
        EnergyMarket.from_csv(path)


def test_generation_is_reproducible_and_does_not_mutate_input():
    prices = generate_hourly_prices(days=1, seed=42)
    pd.testing.assert_frame_equal(prices, generate_hourly_prices(days=1, seed=42))
    market = EnergyMarket(prices)
    prices.loc[0, "price_chf_kwh"] = 999
    assert market.price_at(0)[1] != 999
    assert len(market) == 24


def test_utc_time_series_spans_daylight_saving_without_gap():
    dates = pd.date_range("2026-10-25 00:00", periods=5, freq="h", tz="UTC")
    market = EnergyMarket(pd.DataFrame({"timestamp": dates, "price_chf_kwh": [.05] * 5}))
    assert market.duration_h == 1
