from models.battery import Battery
from strategies.base import Action, ActionType


class ThresholdStrategy:
    def __init__(self, buy_below: float = 0.08, sell_above: float = 0.20) -> None:
        self.buy_below = buy_below
        self.sell_above = sell_above

    def decide(
        self,
        price_chf_kwh: float,
        batteries: list[Battery],
        duration_h: float = 1.0,
    ) -> list[Action]:
        actions: list[Action] = []
        for battery in batteries:
            if price_chf_kwh < self.buy_below:
                actions.append(Action(battery.id, ActionType.CHARGE))
            elif price_chf_kwh > self.sell_above:
                actions.append(Action(battery.id, ActionType.DISCHARGE))
            else:
                actions.append(Action(battery.id, ActionType.IDLE))
        return actions
