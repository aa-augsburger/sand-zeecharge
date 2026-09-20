from datetime import datetime
from pathlib import Path

from models.battery import Battery
from models.company import Company
from reports.report import print_summary, save_plots
from simulation.engine import SimulationEngine
from simulation.market import EnergyMarket
from strategies.threshold import ThresholdStrategy

PRICES_PATH = Path("data/prices.csv")
SIMULATION_DAYS = 30
INITIAL_CAPITAL_CHF = 100_000.0


def main() -> None:
    if PRICES_PATH.exists():
        market = EnergyMarket.from_csv(PRICES_PATH)
    else:
        market = EnergyMarket.generate_and_save(
            PRICES_PATH,
            days=SIMULATION_DAYS,
            seed=42,
            start=datetime(2026, 1, 1, 0, 0, 0),
        )

    company = Company(cash_chf=INITIAL_CAPITAL_CHF)
    start_ts = market.price_at(0)[0]
    start_dt = start_ts.to_pydatetime() if hasattr(start_ts, "to_pydatetime") else start_ts

    battery = Battery(
        id="bat-001",
        nominal_capacity_kwh=100.0,
        state_of_health=0.85,
        state_of_charge_kwh=0.0,
        max_charge_kw=40.0,
        max_discharge_kw=40.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        purchase_price_chf=5_000.0,
    )
    company.buy_battery(battery, start_dt)

    strategy = ThresholdStrategy(buy_below=0.08, sell_above=0.20)
    engine = SimulationEngine(duration_h=1.0)
    result = engine.run(
        market,
        company,
        strategy,
        initial_capital_chf=INITIAL_CAPITAL_CHF,
    )

    print_summary(company, result, simulation_days=SIMULATION_DAYS)
    save_plots(result)
    print(f"Plots saved to reports/output/")


if __name__ == "__main__":
    main()
