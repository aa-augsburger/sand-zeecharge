import csv
import io
import json
from collections import deque
from pathlib import Path

from models.company import Company
from simulation.engine import SimulationResult


def print_summary(company: Company, result: SimulationResult, simulation_days: float | None = None) -> None:
    from ui.console import build_final_report, console
    console.print(build_final_report(company, result))


def export_results(company: Company, result: SimulationResult, output_dir: Path | str) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "simulated_days": result.simulated_days,
        "timestep_h": result.duration_h,
        "initial_capital_chf": result.initial_capital_chf,
        "final_cash_chf": company.cash_chf,
        "battery_investment_chf": company.battery_purchase_cost,
        "energy_cost_chf": company.total_energy_cost,
        "energy_revenue_chf": company.total_revenue,
        "maintenance_chf": company.maintenance_cost,
        "trading_margin_chf": company.trading_pnl(),
        "cash_result_after_investment_chf": company.net_profit(),
        "purchased_kwh": result.purchased_kwh,
        "sold_kwh": result.sold_kwh,
        "initial_soc_kwh": sum(result.initial_soc_kwh.values()),
        "final_soc_kwh": result.soc_kwh[-1],
        "conversion_losses_kwh": result.conversion_losses_kwh,
        "degradation_losses_kwh": result.degradation_losses_kwh,
        "energy_balance_error_kwh": result.energy_balance_error_kwh,
        "observed_round_trip_efficiency": result.round_trip_efficiency,
        "batteries": [{"id": b.id, "soh": b.state_of_health, "soc_kwh": b.state_of_charge_kwh,
                       "nominal_equivalent_cycles": b.equivalent_cycles()} for b in company.batteries],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    with (output / "transactions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "type", "battery_id", "energy_kwh", "price_chf_kwh", "total_chf"])
        for tx in company.transactions:
            # Prefix user-controlled spreadsheet formulas while preserving ordinary IDs.
            identifier = tx.battery_id or ""
            if identifier.lstrip().startswith(("=", "+", "-", "@")):
                identifier = "'" + identifier
            writer.writerow([tx.timestamp.isoformat(), tx.transaction_type.value, identifier,
                             tx.energy_kwh, tx.price_chf_kwh, tx.total_chf])
    with (output / "steps.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "duration_h", "price_chf_kwh", "soc_kwh", "cash_chf", "trading_margin_chf"])
        for step, soc in zip(result.steps, result.soc_kwh):
            writer.writerow([step.timestamp.isoformat(), step.duration_h, step.price_chf_kwh,
                             soc, step.cash_chf, step.trading_pnl_chf])


def save_html_report(company: Company, result: SimulationResult, path: Path | str) -> None:
    from rich.console import Console
    from rich.terminal_theme import MONOKAI
    from ui.console import build_dashboard, build_final_report
    output = Console(record=True, width=115, file=io.StringIO())
    recent = deque(maxlen=5)
    for step in result.steps:
        recent.extendleft(step.transactions)
    output.print(build_dashboard(result.steps[-1], recent, width=115))
    output.print(build_final_report(company, result))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save_html(str(destination), theme=MONOKAI)


def save_plots(result: SimulationResult, output_dir: Path | str = "reports/output") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    charts = [
        ("price", result.prices_chf_kwh, "Prix de l’électricité", "CHF/kWh", "#22d3ee"),
        ("soc", result.soc_kwh, "Énergie stockée dans le parc", "kWh", "#34d399"),
        ("cumulative_profit", result.cumulative_profit_chf, "Solde après investissement", "CHF", "#c084fc"),
    ]
    with plt.style.context("dark_background"):
        for name, values, title, unit, color in charts:
            fig, ax = plt.subplots(figsize=(11, 4))
            fig.patch.set_facecolor("#111827")
            ax.set_facecolor("#111827")
            ax.plot(result.timestamps, values, color=color, linewidth=1.2)
            ax.set(title=title, ylabel=unit, xlabel="Date")
            ax.grid(alpha=0.15)
            fig.autofmt_xdate()
            fig.tight_layout()
            fig.savefig(output / f"{name}.png", dpi=140)
            plt.close(fig)
