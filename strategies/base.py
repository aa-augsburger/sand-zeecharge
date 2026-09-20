from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from models.battery import Battery


class ActionType(Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"


@dataclass(frozen=True)
class Action:
    battery_id: str
    action_type: ActionType


class TradingStrategy(Protocol):
    def decide(
        self,
        price_chf_kwh: float,
        batteries: list[Battery],
        duration_h: float,
    ) -> list[Action]: ...
