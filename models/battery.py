from dataclasses import dataclass

from models.validation import finite

# SoH loss per nominal equivalent full cycle (charge + discharge).
DEFAULT_DEGRADATION_FACTOR = 0.00005


def apply_degradation(state_of_health: float, energy_cycled_kwh: float,
                      nominal_capacity_kwh: float,
                      degradation_factor: float = DEFAULT_DEGRADATION_FACTOR) -> float:
    finite("SOH", state_of_health, 0, 1)
    finite("énergie cyclée", energy_cycled_kwh, 0)
    finite("capacité nominale", nominal_capacity_kwh, positive=True)
    finite("dégradation", degradation_factor, 0, 1)
    return max(0.0, state_of_health - energy_cycled_kwh / (2 * nominal_capacity_kwh) * degradation_factor)


@dataclass
class Battery:
    id: str
    nominal_capacity_kwh: float
    state_of_health: float
    state_of_charge_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    charge_efficiency: float
    discharge_efficiency: float
    purchase_price_chf: float
    total_energy_charged_kwh: float = 0.0
    total_energy_discharged_kwh: float = 0.0
    degradation_factor: float = DEFAULT_DEGRADATION_FACTOR
    degradation_losses_kwh: float = 0.0

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Identifiant de batterie vide")
        finite("capacité nominale", self.nominal_capacity_kwh, positive=True)
        finite("SOH", self.state_of_health, 0, 1)
        finite("SOC", self.state_of_charge_kwh, 0, self.usable_capacity_kwh)
        for name in ("max_charge_kw", "max_discharge_kw", "purchase_price_chf",
                     "total_energy_charged_kwh", "total_energy_discharged_kwh", "degradation_losses_kwh"):
            finite(name, getattr(self, name), 0)
        for name in ("charge_efficiency", "discharge_efficiency"):
            finite(name, getattr(self, name), maximum=1, positive=True)
        finite("dégradation", self.degradation_factor, 0, 1)

    @property
    def usable_capacity_kwh(self) -> float:
        return self.nominal_capacity_kwh * self.state_of_health

    @property
    def cycles(self) -> float:
        return self.equivalent_cycles()

    def equivalent_cycles(self) -> float:
        """Throughput EFC, referenced to fixed nominal capacity, never current SoH."""
        return (self.total_energy_charged_kwh + self.total_energy_discharged_kwh) / (2 * self.nominal_capacity_kwh)

    def _degrade(self, energy: float) -> None:
        self.state_of_health = apply_degradation(
            self.state_of_health, energy, self.nominal_capacity_kwh, self.degradation_factor)
        lost = max(0.0, self.state_of_charge_kwh - self.usable_capacity_kwh)
        self.degradation_losses_kwh += lost
        self.state_of_charge_kwh = min(self.state_of_charge_kwh, self.usable_capacity_kwh)

    def charge(self, grid_kwh: float, duration_h: float = 1.0) -> float:
        """Charge power is measured on the grid side; return grid energy purchased."""
        self.validate()
        finite("énergie demandée", grid_kwh, 0)
        finite("durée", duration_h, positive=True)
        actual = min(grid_kwh, self.max_charge_kw * duration_h,
                     (self.usable_capacity_kwh - self.state_of_charge_kwh) / self.charge_efficiency)
        stored = actual * self.charge_efficiency
        self.state_of_charge_kwh += stored
        self.total_energy_charged_kwh += stored
        self._degrade(stored)
        return actual

    def discharge(self, request_battery_kwh: float, duration_h: float = 1.0) -> float:
        """Discharge power is measured inside the battery; return energy sold to grid."""
        self.validate()
        finite("énergie demandée", request_battery_kwh, 0)
        finite("durée", duration_h, positive=True)
        removed = min(request_battery_kwh, self.max_discharge_kw * duration_h, self.state_of_charge_kwh)
        self.state_of_charge_kwh -= removed
        self.total_energy_discharged_kwh += removed
        self._degrade(removed)
        return removed * self.discharge_efficiency
