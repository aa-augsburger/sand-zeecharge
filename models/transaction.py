from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isclose

from models.validation import finite


class TransactionType(Enum):
    BUY_ENERGY = "buy_energy"
    SELL_ENERGY = "sell_energy"
    BATTERY_PURCHASE = "battery_purchase"
    MAINTENANCE = "maintenance"


@dataclass(frozen=True)
class Transaction:
    timestamp: datetime
    transaction_type: TransactionType
    battery_id: str | None
    energy_kwh: float
    price_chf_kwh: float
    total_chf: float

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise ValueError("Horodatage de transaction invalide")
        if not isinstance(self.transaction_type, TransactionType):
            raise ValueError("Type de transaction invalide")
        finite("énergie", self.energy_kwh, 0)
        finite("prix", self.price_chf_kwh)
        finite("montant", self.total_chf)
        if self.transaction_type in (TransactionType.BUY_ENERGY, TransactionType.SELL_ENERGY):
            if not isclose(self.total_chf, self.energy_kwh * self.price_chf_kwh, abs_tol=1e-9):
                raise ValueError("Montant incohérent avec énergie × prix")
        else:
            finite("montant", self.total_chf, 0)
