import pytest

from models.battery import Battery


@pytest.fixture
def battery_factory():
    def create(id="B001", **changes):
        fields = dict(id=id, nominal_capacity_kwh=100.0, state_of_health=1.0,
                      state_of_charge_kwh=0.0, max_charge_kw=100.0, max_discharge_kw=100.0,
                      charge_efficiency=1.0, discharge_efficiency=1.0,
                      purchase_price_chf=0.0, degradation_factor=0.0)
        fields.update(changes)
        return Battery(**fields)
    return create
