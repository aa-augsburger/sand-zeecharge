from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from models.battery import Battery
from models.company import Company
from models.transaction import Transaction, TransactionType
from simulation.market import EnergyMarket
from strategies.base import ActionType, TradingStrategy


@dataclass
class SimulationResult:
    timestamps: list[pd.Timestamp] = field(default_factory=list)
    prices_chf_kwh: list[float] = field(default_factory=list)
    soc_kwh: list[float] = field(default_factory=list)
    cumulative_profit_chf: list[float] = field(default_factory=list)
    initial_capital_chf: float = 0.0
    initial_soh: dict[str, float] = field(default_factory=dict)


class SimulationEngine:
    def __init__(self, duration_h: float = 1.0) -> None:
        self.duration_h = duration_h

    def run(
        self,
        market: EnergyMarket,
        company: Company,
        strategy: TradingStrategy,
        initial_capital_chf: float | None = None,
    ) -> SimulationResult:
        if initial_capital_chf is None:
            initial_capital_chf = company.cash_chf + company.battery_purchase_cost

        result = SimulationResult(
            initial_capital_chf=initial_capital_chf,
            initial_soh={b.id: b.state_of_health for b in company.batteries},
        )

        for index in range(len(market)):
            timestamp, price = market.price_at(index)
            ts = timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else timestamp

            actions = strategy.decide(price, company.batteries, self.duration_h)
            self._apply_actions(company, actions, ts, price)

            total_soc = sum(b.state_of_charge_kwh for b in company.batteries)
            result.timestamps.append(timestamp)
            result.prices_chf_kwh.append(price)
            result.soc_kwh.append(total_soc)
            result.cumulative_profit_chf.append(company.net_profit())

        return result

    def _apply_actions(
        self,
        company: Company,
        actions: list,
        timestamp: datetime,
        price_chf_kwh: float,
    ) -> None:
        battery_by_id = {b.id: b for b in company.batteries}

        for action in actions:
            battery = battery_by_id.get(action.battery_id)
            if battery is None:
                continue

            if action.action_type == ActionType.CHARGE:
                self._charge_battery(company, battery, timestamp, price_chf_kwh)
            elif action.action_type == ActionType.DISCHARGE:
                self._discharge_battery(company, battery, timestamp, price_chf_kwh)

    def _charge_battery(
        self,
        company: Company,
        battery: Battery,
        timestamp: datetime,
        price_chf_kwh: float,
    ) -> None:
        max_grid = battery.max_charge_kw * self.duration_h
        grid_used = battery.charge(max_grid, self.duration_h)
        if grid_used <= 0:
            return
        cost = grid_used * price_chf_kwh
        company.record_energy_purchase(
            Transaction(
                timestamp=timestamp,
                transaction_type=TransactionType.BUY_ENERGY,
                battery_id=battery.id,
                energy_kwh=grid_used,
                price_chf_kwh=price_chf_kwh,
                total_chf=cost,
            )
        )

    def _discharge_battery(
        self,
        company: Company,
        battery: Battery,
        timestamp: datetime,
        price_chf_kwh: float,
    ) -> None:
        max_from_battery = battery.max_discharge_kw * self.duration_h
        grid_sold = battery.discharge(max_from_battery, self.duration_h)
        if grid_sold <= 0:
            return
        revenue = grid_sold * price_chf_kwh
        company.record_energy_sale(
            Transaction(
                timestamp=timestamp,
                transaction_type=TransactionType.SELL_ENERGY,
                battery_id=battery.id,
                energy_kwh=grid_sold,
                price_chf_kwh=price_chf_kwh,
                total_chf=revenue,
            )
        )
