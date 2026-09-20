from dataclasses import dataclass

# SoH loss per kWh cycled relative to one full nominal cycle (1.0 = 100% SoH lost per full cycle)
DEFAULT_DEGRADATION_FACTOR = 0.000_05


def apply_degradation(
    state_of_health: float,
    energy_cycled_kwh: float,
    nominal_capacity_kwh: float,
    degradation_factor: float = DEFAULT_DEGRADATION_FACTOR,
) -> float:
    """Reduce SoH based on energy throughput. Replace this function for richer models."""
    if energy_cycled_kwh <= 0 or nominal_capacity_kwh <= 0:
        return state_of_health
    loss = (energy_cycled_kwh / nominal_capacity_kwh) * degradation_factor
    return max(0.0, state_of_health - loss)


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
    cycles: float = 0.0
    total_energy_charged_kwh: float = 0.0
    total_energy_discharged_kwh: float = 0.0
    degradation_factor: float = DEFAULT_DEGRADATION_FACTOR

    @property
    def usable_capacity_kwh(self) -> float:
        return self.nominal_capacity_kwh * self.state_of_health

    def _clamp_soc(self) -> None:
        cap = self.usable_capacity_kwh
        self.state_of_charge_kwh = max(0.0, min(self.state_of_charge_kwh, cap))

    def _record_cycle_contribution(self, energy_kwh: float) -> None:
        cap = self.usable_capacity_kwh
        if cap > 0:
            self.cycles += energy_kwh / (2.0 * cap)

    def charge(self, grid_kwh: float, duration_h: float = 1.0) -> float:
        """Draw grid_kwh from the grid (limited by power and headroom). Returns actual grid kWh used."""
        if grid_kwh <= 0:
            return 0.0

        max_energy = self.max_charge_kw * duration_h
        headroom = self.usable_capacity_kwh - self.state_of_charge_kwh
        max_storable = headroom / self.charge_efficiency if self.charge_efficiency > 0 else 0.0

        actual_grid = min(grid_kwh, max_energy, max_storable)
        if actual_grid <= 0:
            return 0.0

        stored = actual_grid * self.charge_efficiency
        self.state_of_charge_kwh += stored
        self._clamp_soc()

        self.total_energy_charged_kwh += stored
        self._record_cycle_contribution(stored)
        self.state_of_health = apply_degradation(
            self.state_of_health,
            stored,
            self.nominal_capacity_kwh,
            self.degradation_factor,
        )
        self._clamp_soc()
        return actual_grid

    def discharge(self, request_battery_kwh: float, duration_h: float = 1.0) -> float:
        """Remove energy from the battery (limited by power and SOC). Returns kWh delivered to the grid."""
        if request_battery_kwh <= 0:
            return 0.0

        max_energy = self.max_discharge_kw * duration_h
        from_battery = min(request_battery_kwh, max_energy, self.state_of_charge_kwh)
        if from_battery <= 0:
            return 0.0

        to_grid = from_battery * self.discharge_efficiency
        self.state_of_charge_kwh -= from_battery
        self._clamp_soc()

        self.total_energy_discharged_kwh += from_battery
        self._record_cycle_contribution(from_battery)
        self.state_of_health = apply_degradation(
            self.state_of_health,
            from_battery,
            self.nominal_capacity_kwh,
            self.degradation_factor,
        )
        self._clamp_soc()
        return to_grid

    def equivalent_cycles(self) -> float:
        cap = self.usable_capacity_kwh
        if cap <= 0:
            return 0.0
        return self.total_energy_discharged_kwh / (2.0 * cap)
