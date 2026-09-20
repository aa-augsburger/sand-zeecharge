from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TransactionType(Enum):
    BUY_ENERGY = "buy_energy"
    SELL_ENERGY = "sell_energy"
    BATTERY_PURCHASE = "battery_purchase"


@dataclass(frozen=True)
class Transaction:
    timestamp: datetime
    transaction_type: TransactionType
    battery_id: str | None
    energy_kwh: float
    price_chf_kwh: float
    total_chf: float
