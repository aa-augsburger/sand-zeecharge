from datetime import datetime

import pandas as pd
import pytest

from models.company import Company
from models.transaction import Transaction, TransactionType
from simulation.engine import SimulationEngine
from simulation.market import EnergyMarket
from strategies.base import Action, ActionType
from strategies.threshold import ThresholdStrategy


def market(prices, freq="h"):
    return EnergyMarket(pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=len(prices), freq=freq),
                                      "price_chf_kwh": prices}))


def test_complete_cycle_and_fixed_nominal_reference(battery_factory):
    b = battery_factory()
    b.charge(100)
    b.discharge(100)
    assert b.cycles == b.equivalent_cycles() == 1
    b.state_of_health = 0.8
    assert b.equivalent_cycles() == 1


def test_full_nominal_cycle_applies_one_degradation_factor(battery_factory):
    b = battery_factory(degradation_factor=0.02)
    b.charge(50)
    b.discharge(50)
    b.charge(50)
    b.discharge(50)
    assert b.cycles == 1
    assert b.state_of_health == pytest.approx(0.98)


@pytest.mark.parametrize("changes", [
    {"charge_efficiency": 2}, {"discharge_efficiency": 0}, {"nominal_capacity_kwh": 0},
    {"state_of_health": 1.1}, {"state_of_charge_kwh": -1}, {"state_of_charge_kwh": 101},
    {"max_charge_kw": -1}, {"purchase_price_chf": -1}, {"degradation_factor": -1},
    {"state_of_health": float("nan")}, {"max_discharge_kw": float("inf")}, {"id": ""},
])
def test_invalid_batteries_are_rejected(battery_factory, changes):
    with pytest.raises(ValueError):
        battery_factory(**changes)


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf")])
def test_invalid_duration_is_rejected(battery_factory, duration):
    with pytest.raises(ValueError):
        battery_factory().charge(10, duration)
    with pytest.raises(ValueError):
        SimulationEngine(duration)


def test_energy_conservation_with_degradation_and_nonempty_start(battery_factory):
    b = battery_factory(state_of_charge_kwh=30, charge_efficiency=.95,
                        discharge_efficiency=.9, degradation_factor=.02)
    c = Company(100, [b])
    result = SimulationEngine().run(market([.05, .05, .25, .06, .3]), c, ThresholdStrategy())
    assert result.energy_balance_error_kwh == pytest.approx(0, abs=1e-9)
    assert result.degradation_losses_kwh > 0
    assert result.conversion_losses_kwh > 0
    assert result.round_trip_efficiency is None
    assert c.cash_chf == pytest.approx(100 + c.net_profit())


def test_round_trip_efficiency_and_partial_inventory(battery_factory):
    c = Company(100, [battery_factory(charge_efficiency=.95, discharge_efficiency=.95)])
    result = SimulationEngine().run(market([.05, .25]), c, ThresholdStrategy())
    assert result.round_trip_efficiency == pytest.approx(.9025)
    assert result.energy_balance_error_kwh == pytest.approx(0, abs=1e-9)
    result = SimulationEngine().run(market([.05]), c, ThresholdStrategy())
    assert result.round_trip_efficiency is None
    assert result.energy_balance_error_kwh == pytest.approx(0, abs=1e-9)


@pytest.mark.parametrize("cash, expected_energy", [(0, 0), (1, 20), (2, 40)])
def test_charge_is_limited_by_cash(battery_factory, cash, expected_energy):
    c = Company(cash, [battery_factory(max_charge_kw=40)])
    SimulationEngine().run(market([.05]), c, ThresholdStrategy())
    assert c.total_energy_purchased_kwh == pytest.approx(expected_energy)
    assert c.cash_chf == pytest.approx(0)


def test_negative_and_zero_purchase_prices(battery_factory):
    c = Company(0, [battery_factory(max_charge_kw=40)])
    result = SimulationEngine().run(market([-.05, 0]), c, ThresholdStrategy())
    assert c.cash_chf == 2
    assert c.total_energy_purchased_kwh == 80
    assert result.energy_balance_error_kwh == 0


def test_negative_price_sale_cannot_overdraw_cash(battery_factory):
    c = Company(1, [battery_factory(state_of_charge_kwh=100)])
    SimulationEngine().run(market([-.1]), c, ThresholdStrategy(-.5, -.2))
    assert c.total_energy_sold_kwh == 10
    assert c.cash_chf == 0
    assert c.batteries[0].state_of_charge_kwh == 90


def test_quarter_hour_data_and_explicit_duration_mismatch(battery_factory):
    c = Company(100, [battery_factory(max_charge_kw=40)])
    m = market([.05, .05], "15min")
    result = SimulationEngine().run(m, c, ThresholdStrategy())
    assert result.purchased_kwh == 20
    assert result.simulated_days == pytest.approx(.5 / 24)
    with pytest.raises(ValueError, match="durée"):
        SimulationEngine(1).run(m, c, ThresholdStrategy())


def test_snapshots_include_all_batteries_and_do_not_change(battery_factory):
    c = Company(100, [battery_factory("A", max_charge_kw=40), battery_factory("B", max_charge_kw=40)])
    received = []
    def callback(step):
        assert step.cash_chf == c.cash_chf
        received.append(step)
    result = SimulationEngine().run(market([.05, .25]), c, ThresholdStrategy(), on_step=callback)
    assert received[0].cash_chf == 96
    assert len(received[0].transactions) == 2
    assert [b.after.soc_kwh for b in received[0].batteries] == [40, 40]
    assert c.cash_chf == 116
    assert result.energy_balance_error_kwh == 0


def test_scarce_cash_has_documented_portfolio_priority(battery_factory):
    c = Company(3, [battery_factory("A", max_charge_kw=40), battery_factory("B", max_charge_kw=40)])
    SimulationEngine().run(market([.05]), c, ThresholdStrategy())
    assert [b.state_of_charge_kwh for b in c.batteries] == [40, 20]
    assert c.cash_chf == 0


def test_idle_steps_do_not_repeat_transactions(battery_factory):
    c = Company(100, [battery_factory()])
    result = SimulationEngine().run(market([.05, .12, .12]), c, ThresholdStrategy())
    assert [len(s.transactions) for s in result.steps] == [1, 0, 0]


def test_duplicate_and_unknown_actions_fail_before_any_transfer(battery_factory):
    class BadStrategy:
        def decide(self, price, batteries, duration):
            return [Action("B001", ActionType.CHARGE), Action("B001", ActionType.DISCHARGE)]
    c = Company(100, [battery_factory()])
    with pytest.raises(ValueError, match="multiples"):
        SimulationEngine().run(market([.05]), c, BadStrategy())
    assert c.cash_chf == 100
    assert c.batteries[0].state_of_charge_kwh == 0


def test_duplicate_battery_id_and_maintenance(battery_factory):
    c = Company(100)
    c.buy_battery(battery_factory(purchase_price_chf=10), datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        c.buy_battery(battery_factory(), datetime(2026, 1, 1))
    c.record_maintenance(5, datetime(2026, 1, 1))
    assert c.cash_chf == 85
    assert c.net_profit() == -15
    with pytest.raises(ValueError):
        c.record_maintenance(100, datetime(2026, 1, 1))
    assert c.cash_chf == 85


def test_transaction_amount_and_type_validation():
    with pytest.raises(ValueError):
        Transaction(datetime(2026, 1, 1), TransactionType.BUY_ENERGY, "b", 10, .05, 100)
    tx = Transaction(datetime(2026, 1, 1), TransactionType.SELL_ENERGY, "b", 10, .05, .5)
    with pytest.raises(ValueError):
        Company(100).record_energy_purchase(tx)


@pytest.mark.parametrize("buy,sell", [(1, 1), (2, 1), (float("nan"), 1), (0, float("inf"))])
def test_invalid_strategy_thresholds(buy, sell):
    with pytest.raises(ValueError):
        ThresholdStrategy(buy, sell)
