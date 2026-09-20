from datetime import datetime

import pandas as pd

from models.battery import Battery
from models.company import Company
from models.transaction import Transaction, TransactionType
from simulation.engine import SimulationEngine
from simulation.market import EnergyMarket
from strategies.threshold import ThresholdStrategy


def test_company_pays_on_energy_purchase() -> None:
    company = Company(cash_chf=1000.0)
    tx = Transaction(
        timestamp=datetime(2026, 1, 1),
        transaction_type=TransactionType.BUY_ENERGY,
        battery_id="b1",
        energy_kwh=10.0,
        price_chf_kwh=0.10,
        total_chf=1.0,
    )
    company.record_energy_purchase(tx)
    assert company.cash_chf == 999.0
    assert company.total_energy_cost == 1.0


def test_company_receives_on_energy_sale() -> None:
    company = Company(cash_chf=1000.0)
    tx = Transaction(
        timestamp=datetime(2026, 1, 1),
        transaction_type=TransactionType.SELL_ENERGY,
        battery_id="b1",
        energy_kwh=5.0,
        price_chf_kwh=0.30,
        total_chf=1.5,
    )
    company.record_energy_sale(tx)
    assert company.cash_chf == 1001.5
    assert company.total_revenue == 1.5


def test_mini_simulation_with_fixed_prices() -> None:
    prices = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=3, freq="h"),
            "price_chf_kwh": [0.05, 0.25, 0.06],
        }
    )
    market = EnergyMarket(prices)
    company = Company(cash_chf=10_000.0)
    bat = Battery(
        id="b1",
        nominal_capacity_kwh=100.0,
        state_of_health=1.0,
        state_of_charge_kwh=0.0,
        max_charge_kw=40.0,
        max_discharge_kw=40.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        purchase_price_chf=0.0,
        degradation_factor=0.0,
    )
    company.batteries.append(bat)

    engine = SimulationEngine()
    engine.run(market, company, ThresholdStrategy(buy_below=0.08, sell_above=0.20))

    assert company.total_energy_purchased_kwh > 0
    assert company.total_energy_sold_kwh > 0
