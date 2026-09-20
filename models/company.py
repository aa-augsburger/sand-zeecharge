from dataclasses import dataclass, field
from datetime import datetime

from models.battery import Battery
from models.transaction import Transaction, TransactionType


@dataclass
class Company:
    cash_chf: float
    batteries: list[Battery] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)
    total_revenue: float = 0.0
    total_energy_cost: float = 0.0
    maintenance_cost: float = 0.0
    battery_purchase_cost: float = 0.0
    total_energy_purchased_kwh: float = 0.0
    total_energy_sold_kwh: float = 0.0

    def buy_battery(self, battery: Battery, timestamp: datetime) -> None:
        if self.cash_chf < battery.purchase_price_chf:
            raise ValueError("Insufficient cash to buy battery")
        self.cash_chf -= battery.purchase_price_chf
        self.battery_purchase_cost += battery.purchase_price_chf
        self.batteries.append(battery)
        self.transactions.append(
            Transaction(
                timestamp=timestamp,
                transaction_type=TransactionType.BATTERY_PURCHASE,
                battery_id=battery.id,
                energy_kwh=0.0,
                price_chf_kwh=0.0,
                total_chf=battery.purchase_price_chf,
            )
        )

    def record_energy_purchase(self, tx: Transaction) -> None:
        self.cash_chf -= tx.total_chf
        self.total_energy_cost += tx.total_chf
        self.total_energy_purchased_kwh += tx.energy_kwh
        self.transactions.append(tx)

    def record_energy_sale(self, tx: Transaction) -> None:
        self.cash_chf += tx.total_chf
        self.total_revenue += tx.total_chf
        self.total_energy_sold_kwh += tx.energy_kwh
        self.transactions.append(tx)

    def net_profit(self) -> float:
        return (
            self.total_revenue
            - self.total_energy_cost
            - self.battery_purchase_cost
            - self.maintenance_cost
        )
