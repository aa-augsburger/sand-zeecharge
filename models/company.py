from dataclasses import dataclass, field
from datetime import datetime

from models.battery import Battery
from models.transaction import Transaction, TransactionType
from models.validation import finite


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

    def __post_init__(self) -> None:
        finite("trésorerie", self.cash_chf, 0)
        self.validate_batteries()

    def validate_batteries(self) -> None:
        ids = [b.id for b in self.batteries]
        if len(ids) != len(set(ids)):
            raise ValueError("Identifiants de batteries dupliqués")
        for battery in self.batteries:
            battery.validate()

    def buy_battery(self, battery: Battery, timestamp: datetime) -> None:
        battery.validate()
        if any(b.id == battery.id for b in self.batteries):
            raise ValueError("Identifiant de batterie déjà utilisé")
        if self.cash_chf < battery.purchase_price_chf:
            raise ValueError("Insufficient cash to buy battery")
        tx = Transaction(timestamp, TransactionType.BATTERY_PURCHASE, battery.id,
                         0.0, 0.0, battery.purchase_price_chf)
        self.cash_chf -= battery.purchase_price_chf
        self.battery_purchase_cost += battery.purchase_price_chf
        self.batteries.append(battery)
        self.transactions.append(tx)

    def record_energy_purchase(self, tx: Transaction) -> None:
        if tx.transaction_type != TransactionType.BUY_ENERGY:
            raise ValueError("Transaction d'achat attendue")
        if tx.total_chf > self.cash_chf + 1e-9:
            raise ValueError("Trésorerie insuffisante")
        self.cash_chf = max(0.0, self.cash_chf - tx.total_chf)
        self.total_energy_cost += tx.total_chf
        self.total_energy_purchased_kwh += tx.energy_kwh
        self.transactions.append(tx)

    def record_energy_sale(self, tx: Transaction) -> None:
        if tx.transaction_type != TransactionType.SELL_ENERGY:
            raise ValueError("Transaction de vente attendue")
        if self.cash_chf + tx.total_chf < -1e-9:
            raise ValueError("Trésorerie insuffisante pour une vente à prix négatif")
        self.cash_chf = max(0.0, self.cash_chf + tx.total_chf)
        self.total_revenue += tx.total_chf
        self.total_energy_sold_kwh += tx.energy_kwh
        self.transactions.append(tx)

    def record_maintenance(self, amount: float, timestamp: datetime) -> None:
        finite("maintenance", amount, 0)
        if amount > self.cash_chf:
            raise ValueError("Trésorerie insuffisante")
        tx = Transaction(timestamp, TransactionType.MAINTENANCE, None, 0, 0, amount)
        self.cash_chf -= amount
        self.maintenance_cost += amount
        self.transactions.append(tx)

    def trading_pnl(self) -> float:
        return self.total_revenue - self.total_energy_cost

    def net_profit(self) -> float:
        """Cash result after investment, not accounting profit or asset valuation."""
        return (
            self.total_revenue
            - self.total_energy_cost
            - self.battery_purchase_cost
            - self.maintenance_cost
        )
