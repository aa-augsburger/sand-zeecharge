from dataclasses import dataclass, field
from datetime import datetime
from math import isclose
from typing import Callable

import pandas as pd

from models.battery import Battery
from models.company import Company
from models.transaction import Transaction, TransactionType
from models.validation import finite
from simulation.market import EnergyMarket
from strategies.base import Action, ActionType, TradingStrategy


@dataclass(frozen=True)
class BatteryState:
    id: str
    soc_kwh: float
    capacity_kwh: float
    soh: float
    cycles: float

    @classmethod
    def capture(cls, battery: Battery) -> "BatteryState":
        return cls(battery.id, battery.state_of_charge_kwh, battery.usable_capacity_kwh,
                   battery.state_of_health, battery.equivalent_cycles())


@dataclass(frozen=True)
class BatteryStep:
    before: BatteryState
    after: BatteryState
    action: ActionType
    reason: str
    purchased_kwh: float = 0.0
    sold_kwh: float = 0.0
    conversion_losses_kwh: float = 0.0
    degradation_losses_kwh: float = 0.0
    cash_delta_chf: float = 0.0


@dataclass(frozen=True)
class StepResult:
    step_index: int
    total_steps: int
    timestamp: datetime
    duration_h: float
    price_chf_kwh: float
    batteries: tuple[BatteryStep, ...]
    transactions: tuple[Transaction, ...]
    cash_chf: float
    trading_pnl_chf: float
    cash_result_chf: float
    purchased_total_kwh: float
    sold_total_kwh: float
    losses_total_kwh: float


@dataclass
class SimulationResult:
    timestamps: list[pd.Timestamp] = field(default_factory=list)
    prices_chf_kwh: list[float] = field(default_factory=list)
    soc_kwh: list[float] = field(default_factory=list)
    cumulative_profit_chf: list[float] = field(default_factory=list)
    initial_capital_chf: float = 0.0
    initial_soh: dict[str, float] = field(default_factory=dict)
    initial_soc_kwh: dict[str, float] = field(default_factory=dict)
    steps: list[StepResult] = field(default_factory=list)
    duration_h: float = 1.0
    purchased_kwh: float = 0.0
    sold_kwh: float = 0.0
    conversion_losses_kwh: float = 0.0
    degradation_losses_kwh: float = 0.0

    @property
    def simulated_days(self) -> float:
        return len(self.timestamps) * self.duration_h / 24

    @property
    def energy_balance_error_kwh(self) -> float:
        final_soc = self.soc_kwh[-1] if self.soc_kwh else sum(self.initial_soc_kwh.values())
        return (sum(self.initial_soc_kwh.values()) + self.purchased_kwh - self.sold_kwh
                - final_soc - self.conversion_losses_kwh - self.degradation_losses_kwh)

    @property
    def round_trip_efficiency(self) -> float | None:
        # An empty-to-empty observation avoids mistaking inventory changes for losses.
        if (self.purchased_kwh <= 0 or sum(self.initial_soc_kwh.values()) > 1e-8
                or not self.soc_kwh or self.soc_kwh[-1] > 1e-8):
            return None
        return self.sold_kwh / self.purchased_kwh


class SimulationEngine:
    def __init__(self, duration_h: float | None = None) -> None:
        if duration_h is not None:
            finite("durée", duration_h, positive=True)
        self.duration_h = duration_h

    def run(self, market: EnergyMarket, company: Company, strategy: TradingStrategy,
            initial_capital_chf: float | None = None,
            on_step: Callable[[StepResult], None] | None = None) -> SimulationResult:
        company.validate_batteries()
        finite("trésorerie", company.cash_chf, 0)
        if not company.batteries:
            raise ValueError("La simulation nécessite au moins une batterie")
        duration = market.duration_h
        if self.duration_h is not None and not isclose(self.duration_h, duration, abs_tol=1e-9):
            raise ValueError("La durée du moteur ne correspond pas à celle du marché")
        if initial_capital_chf is None:
            initial_capital_chf = company.cash_chf - company.net_profit()
        finite("capital initial", initial_capital_chf, 0)
        result = SimulationResult(
            initial_capital_chf=initial_capital_chf, duration_h=duration,
            initial_soh={b.id: b.state_of_health for b in company.batteries},
            initial_soc_kwh={b.id: b.state_of_charge_kwh for b in company.batteries})

        for index in range(len(market)):
            timestamp, price = market.price_at(index)
            ts = timestamp.to_pydatetime()
            finite("prix", price)
            actions = strategy.decide(price, company.batteries, duration)
            by_id = self._validate_actions(actions, company)
            tx_start = len(company.transactions)
            # Stable portfolio order defines priority when cash is scarce.
            outcomes = tuple(self._execute(company, battery, by_id.get(battery.id, ActionType.IDLE),
                                           ts, price, duration) for battery in company.batteries)
            for outcome in outcomes:
                result.purchased_kwh += outcome.purchased_kwh
                result.sold_kwh += outcome.sold_kwh
                result.conversion_losses_kwh += outcome.conversion_losses_kwh
                result.degradation_losses_kwh += outcome.degradation_losses_kwh
            step = StepResult(
                index, len(market), ts, duration, price, outcomes,
                tuple(company.transactions[tx_start:]), company.cash_chf,
                company.trading_pnl(), company.net_profit(), result.purchased_kwh,
                result.sold_kwh, result.conversion_losses_kwh + result.degradation_losses_kwh)
            result.steps.append(step)
            result.timestamps.append(timestamp)
            result.prices_chf_kwh.append(price)
            result.soc_kwh.append(sum(b.state_of_charge_kwh for b in company.batteries))
            result.cumulative_profit_chf.append(company.net_profit())
            if on_step:
                on_step(step)
        return result

    @staticmethod
    def _validate_actions(actions: list[Action], company: Company) -> dict[str, ActionType]:
        known = {b.id for b in company.batteries}
        mapped: dict[str, ActionType] = {}
        for action in actions:
            if action.battery_id not in known:
                raise ValueError(f"Batterie inconnue : {action.battery_id}")
            if action.battery_id in mapped:
                raise ValueError(f"Actions multiples pour {action.battery_id}")
            if not isinstance(action.action_type, ActionType):
                raise ValueError("Action invalide")
            mapped[action.battery_id] = action.action_type
        return mapped

    @staticmethod
    def _execute(company: Company, battery: Battery, action: ActionType,
                 ts: datetime, price: float, duration: float) -> BatteryStep:
        before = BatteryState.capture(battery)
        degradation_before = battery.degradation_losses_kwh
        purchased = sold = conversion = cash_delta = 0.0
        reason = "Aucune opération demandée"
        if action == ActionType.CHARGE:
            physical = min(battery.max_charge_kw * duration,
                           (battery.usable_capacity_kwh - battery.state_of_charge_kwh) / battery.charge_efficiency)
            budget = company.cash_chf / price if price > 0 else physical
            requested = max(0.0, min(physical, budget))
            purchased = battery.charge(requested, duration)
            conversion = purchased * (1 - battery.charge_efficiency)
            cash_delta = -purchased * price
            reason = "Charge" if purchased else "Batterie pleine ou charge impossible"
            if budget < physical:
                reason = "Charge limitée par la trésorerie" if purchased else "Trésorerie insuffisante"
            if purchased:
                company.record_energy_purchase(Transaction(ts, TransactionType.BUY_ENERGY,
                                                          battery.id, purchased, price, -cash_delta))
        elif action == ActionType.DISCHARGE:
            physical = min(battery.max_discharge_kw * duration, battery.state_of_charge_kwh)
            budget = company.cash_chf / (-price * battery.discharge_efficiency) if price < 0 else physical
            requested = max(0.0, min(physical, budget))
            sold = battery.discharge(requested, duration)
            conversion = requested * (1 - battery.discharge_efficiency)
            cash_delta = sold * price
            reason = "Décharge" if sold else "Batterie vide ou décharge impossible"
            if budget < physical:
                reason = "Décharge limitée par la trésorerie" if sold else "Trésorerie insuffisante"
            if sold:
                company.record_energy_sale(Transaction(ts, TransactionType.SELL_ENERGY,
                                                      battery.id, sold, price, cash_delta))
        return BatteryStep(before, BatteryState.capture(battery), action, reason, purchased, sold,
                           conversion, battery.degradation_losses_kwh - degradation_before, cash_delta)
