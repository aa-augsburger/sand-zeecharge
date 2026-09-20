from pathlib import Path

import matplotlib.pyplot as plt

from models.company import Company
from models.transaction import TransactionType
from simulation.engine import SimulationResult


def print_summary(
    company: Company,
    result: SimulationResult,
    simulation_days: float,
) -> None:
    net = company.net_profit()
    roi = (net / result.initial_capital_chf * 100) if result.initial_capital_chf else 0.0

    avg_storage_cost = (
        company.total_energy_cost / company.total_energy_sold_kwh
        if company.total_energy_sold_kwh > 0
        else 0.0
    )

    print("BATTERY COMPANY SIMULATION")
    print()
    print(f"Simulation duration: {simulation_days:.0f} days")
    print()
    print(f"Initial capital:        {result.initial_capital_chf:,.0f} CHF")
    print(f"Final cash:             {company.cash_chf:,.0f} CHF")
    print()
    print(f"Battery purchase:       {company.battery_purchase_cost:,.0f} CHF")
    print(f"Energy purchased:       {company.total_energy_purchased_kwh:,.1f} kWh")
    print(f"Energy sold:            {company.total_energy_sold_kwh:,.1f} kWh")
    print()
    print(f"Energy cost:            {company.total_energy_cost:,.2f} CHF")
    print(f"Energy revenue:         {company.total_revenue:,.2f} CHF")
    print(f"Net profit:             {net:,.2f} CHF")
    print()
    print(f"ROI:                    {roi:.2f} %")
    print(f"Avg storage cost:       {avg_storage_cost:.4f} CHF/kWh (sold)")
    print()

    for battery in company.batteries:
        initial_soh = result.initial_soh.get(battery.id, battery.state_of_health) * 100
        battery_profit = _battery_arbitrage_profit(company, battery.id)
        print("Battery:", battery.id)
        print(f"  Initial SoH:            {initial_soh:.1f} %")
        print(f"  Final SoH:              {battery.state_of_health * 100:.2f} %")
        print(f"  Equivalent cycles:      {battery.equivalent_cycles():.2f}")
        print(f"  Arbitrage margin:       {battery_profit:,.2f} CHF")
        print()


def _battery_arbitrage_profit(company: Company, battery_id: str) -> float:
    revenue = sum(
        t.total_chf
        for t in company.transactions
        if t.battery_id == battery_id and t.transaction_type == TransactionType.SELL_ENERGY
    )
    cost = sum(
        t.total_chf
        for t in company.transactions
        if t.battery_id == battery_id and t.transaction_type == TransactionType.BUY_ENERGY
    )
    return revenue - cost


def save_plots(result: SimulationResult, output_dir: Path | str = "reports/output") -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = result.timestamps

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(ts, result.prices_chf_kwh, color="tab:blue", linewidth=0.8)
    ax.set_title("Electricity price")
    ax.set_ylabel("CHF/kWh")
    ax.set_xlabel("Time")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "price.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(ts, result.soc_kwh, color="tab:green", linewidth=0.8)
    ax.set_title("State of charge (total)")
    ax.set_ylabel("kWh")
    ax.set_xlabel("Time")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "soc.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(ts, result.cumulative_profit_chf, color="tab:orange", linewidth=0.8)
    ax.set_title("Cumulative net profit")
    ax.set_ylabel("CHF")
    ax.set_xlabel("Time")
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "cumulative_profit.png", dpi=120)
    plt.close(fig)
