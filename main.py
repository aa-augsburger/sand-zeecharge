import argparse
import sys
from datetime import datetime
from pathlib import Path

from models.battery import Battery
from models.company import Company
from models.validation import finite
from reports.report import export_results, save_html_report, save_plots
from simulation.engine import SimulationEngine
from simulation.market import EnergyMarket, generate_hourly_prices
from strategies.threshold import ThresholdStrategy
from ui.console import LiveCockpit, build_final_report, console

ROOT = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sand Zeecharge — simulation de batteries avec console Rich")
    parser.add_argument("--days", type=int, default=30, help="Durée des prix synthétiques (défaut : 30 jours)")
    parser.add_argument("--prices", type=Path, help="CSV réel : timestamp,price_chf_kwh ; cadence régulière")
    parser.add_argument("--batteries", type=int, default=1, help="Nombre de batteries")
    parser.add_argument("--cash", type=float, default=100_000, help="Capital initial en CHF")
    parser.add_argument("--battery-price", type=float, default=5_000, help="Prix par batterie en CHF")
    parser.add_argument("--capacity", type=float, default=100, help="Capacité nominale par batterie en kWh")
    parser.add_argument("--soh", type=float, default=0.85, help="État de santé initial entre 0 et 1")
    parser.add_argument("--power", type=float, default=40, help="Puissance max en kW, réseau en charge / batterie en décharge")
    parser.add_argument("--efficiency", type=float, default=0.95, help="Rendement de chaque conversion entre 0 et 1")
    parser.add_argument("--buy", type=float, default=0.08, help="Acheter sous ce prix en CHF/kWh")
    parser.add_argument("--sell", type=float, default=0.20, help="Vendre au-dessus de ce prix en CHF/kWh")
    parser.add_argument("--seed", type=int, default=42, help="Graine des prix synthétiques")
    parser.add_argument("--delay", type=float, default=0.02, help="Pause par pas en console interactive, en secondes")
    parser.add_argument("--no-live", action="store_true", help="Afficher uniquement le cockpit final et le bilan")
    parser.add_argument("--verbose", action="store_true", help="Afficher chaque pas intégralement")
    parser.add_argument("--no-plots", action="store_true", help="Désactiver les graphiques PNG")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "output", help="Dossier des rapports HTML, JSON et CSV")
    return parser


def run_simulation(args: argparse.Namespace):
    finite("pause", args.delay, 0)
    if args.batteries < 1:
        raise ValueError("Il faut au moins une batterie")
    strategy = ThresholdStrategy(args.buy, args.sell)
    market = EnergyMarket.from_csv(args.prices) if args.prices else EnergyMarket(
        generate_hourly_prices(start=datetime(2026, 1, 1), days=args.days, seed=args.seed))
    company = Company(cash_chf=args.cash)
    start = market.price_at(0)[0].to_pydatetime()
    # Validate the whole purchase before changing company state.
    prototype = Battery("B001", args.capacity, args.soh, 0, args.power, args.power,
                        args.efficiency, args.efficiency, args.battery_price)
    if args.batteries * prototype.purchase_price_chf > args.cash:
        raise ValueError("Capital insuffisant pour acheter toutes les batteries")
    for index in range(args.batteries):
        company.buy_battery(Battery(f"B{index + 1:03d}", args.capacity, args.soh, 0,
                                   args.power, args.power, args.efficiency, args.efficiency,
                                   args.battery_price), start)
    console.print("[bold cyan]Sand Zeecharge[/bold cyan]  [dim]• Prix " +
                  ("importés" if args.prices else "synthétiques · graine " + str(args.seed)) + "[/dim]")
    console.print(f"[dim]Stratégie : achat < {args.buy:g}, vente > {args.sell:g} CHF/kWh · "
                  f"{args.batteries} batterie(s) · rendement théorique {args.efficiency ** 2:.2%}[/dim]")
    with LiveCockpit(console, delay=args.delay, live=not args.no_live, verbose=args.verbose) as cockpit:
        result = SimulationEngine().run(market, company, strategy,
                                        initial_capital_chf=args.cash, on_step=cockpit.on_step)
    console.print(build_final_report(company, result))
    export_results(company, result, args.output)
    save_html_report(company, result, args.output / "report.html")
    if not args.no_plots:
        save_plots(result, args.output)
    console.print("Rapports enregistrés :", str(args.output.resolve()), style="bold green", markup=False)
    return company, result


def main() -> None:
    # Windows redirected stdout may default to cp1252, which cannot encode Rich bars.
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    try:
        run_simulation(args)
    except (ValueError, OSError) as exc:
        console.print("Erreur :", str(exc), style="bold red", markup=False)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
