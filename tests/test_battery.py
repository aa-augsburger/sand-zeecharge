from models.battery import Battery, apply_degradation


def _battery(**kwargs) -> Battery:
    defaults = {
        "id": "test",
        "nominal_capacity_kwh": 100.0,
        "state_of_health": 1.0,
        "state_of_charge_kwh": 0.0,
        "max_charge_kw": 50.0,
        "max_discharge_kw": 50.0,
        "charge_efficiency": 0.95,
        "discharge_efficiency": 0.95,
        "purchase_price_chf": 1000.0,
        "degradation_factor": 0.0,
    }
    defaults.update(kwargs)
    return Battery(**defaults)


def test_cannot_charge_above_capacity() -> None:
    bat = _battery(state_of_health=0.8, state_of_charge_kwh=79.0)
    used = bat.charge(100.0)
    assert bat.state_of_charge_kwh <= bat.usable_capacity_kwh + 1e-9
    assert used <= 2.0 / 0.95 + 1e-9


def test_cannot_discharge_below_zero() -> None:
    bat = _battery(state_of_charge_kwh=10.0)
    bat.discharge(100.0)
    assert bat.state_of_charge_kwh >= 0.0


def test_charge_applies_efficiency() -> None:
    bat = _battery()
    grid = bat.charge(40.0)
    assert grid == 40.0
    assert abs(bat.state_of_charge_kwh - 40.0 * 0.95) < 1e-9


def test_discharge_applies_efficiency() -> None:
    bat = _battery(state_of_charge_kwh=40.0)
    to_grid = bat.discharge(40.0)
    assert abs(to_grid - 40.0 * 0.95) < 1e-9
    assert bat.state_of_charge_kwh == 0.0


def test_degradation_reduces_soh() -> None:
    soh = apply_degradation(0.85, energy_cycled_kwh=50.0, nominal_capacity_kwh=100.0)
    assert soh < 0.85
