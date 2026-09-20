from collections import deque
from time import monotonic, sleep

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from models.company import Company
from models.transaction import Transaction, TransactionType
from simulation.engine import SimulationResult, StepResult

console = Console()


def money(value: float) -> str:
    return f"{value:,.2f}".replace(",", "’") + " CHF"


def signed(value: float) -> Text:
    return Text(money(value), style="green" if value >= 0 else "red")


def metrics(rows: list[tuple[str, object]], title: str, color: str = "cyan") -> Panel:
    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(style="dim")
    table.add_column(justify="right")
    for label, value in rows:
        table.add_row(label, value if isinstance(value, Text) else str(value))
    return Panel(table, title=title, border_style=color, padding=(1, 1))


def build_dashboard(step: StepResult, recent: deque[Transaction], *, width: int = 110,
                    compact: bool = False) -> Group:
    """Render immutable end-of-step snapshots, never live mutable company state."""
    title = Text("SAND ZEECHARGE", style="bold cyan")
    title.append("   /   SIMULATEUR D’ARBITRAGE", style="dim")
    header = Panel(Group(
        title,
        Text(f"{step.timestamp:%d.%m.%Y %H:%M}   ·   Pas {step.step_index + 1}/{step.total_steps}"
             f"   ·   Intervalle {step.duration_h:g} h", style="dim"),
        ProgressBar(total=step.total_steps, completed=step.step_index + 1,
                    complete_style="cyan", finished_style="green"),
    ), border_style="cyan")
    market = metrics([
        ("Prix", f"{step.price_chf_kwh:.4f} CHF/kWh"),
        ("Énergie achetée · pas", f"{sum(b.purchased_kwh for b in step.batteries):.2f} kWh"),
        ("Énergie vendue · pas", f"{sum(b.sold_kwh for b in step.batteries):.2f} kWh"),
    ], "MARCHÉ")
    finance = metrics([
        ("Trésorerie", money(step.cash_chf)),
        ("Marge d’arbitrage cumulée", signed(step.trading_pnl_chf)),
        ("Solde après investissement", signed(step.cash_result_chf)),
    ], "FINANCES", "magenta")
    if width >= 100:
        top = Table.grid(expand=True)
        top.add_column(ratio=1)
        top.add_column(ratio=1)
        top.add_row(market, finance)
    else:
        top = Group(market, finance)

    batteries = Table(box=box.SIMPLE, expand=True, padding=(0, 1))
    batteries.add_column("Batterie", style="bold")
    batteries.add_column("Stock / capacité", justify="right")
    batteries.add_column("SOC", min_width=10)
    if width >= 100:
        batteries.add_column("SOH", justify="right")
        batteries.add_column("Cycles", justify="right")
    batteries.add_column("Opération")
    visible_batteries = step.batteries[:4] if compact else step.batteries
    for outcome in visible_batteries:
        b = outcome.after
        pct = 100 * b.soc_kwh / b.capacity_kwh if b.capacity_kwh else 0
        filled = min(10, max(0, round(pct / 10)))
        meter = Text("━" * filled, style="green")
        meter.append("━" * (10 - filled), style="bright_black")
        meter.append(f" {pct:3.0f}%")
        values = [Text(b.id), f"{b.soc_kwh:.1f} / {b.capacity_kwh:.1f} kWh", meter]
        if width >= 100:
            values += [f"{b.soh:.1%}", f"{b.cycles:.2f}"]
        style = "cyan" if outcome.purchased_kwh else "green" if outcome.sold_kwh else "dim"
        reason = "En attente" if outcome.action.value == "idle" else outcome.reason
        values.append(Text(reason, style=style))
        batteries.add_row(*values)

    if compact and len(step.batteries) > 4:
        batteries.caption = f"+ {len(step.batteries) - 4} batteries · parc complet dans le rapport final"

    history = Table(box=box.SIMPLE, expand=True)
    for name in ("Heure", "Batterie", "Opération", "kWh", "Trésorerie"):
        history.add_column(name, justify="right" if name in ("kWh", "Trésorerie") else "left")
    for tx in list(recent)[:2 if compact else 5]:
        buying = tx.transaction_type == TransactionType.BUY_ENERGY
        history.add_row(tx.timestamp.strftime("%d.%m %H:%M"), Text(tx.battery_id or "—"),
                        Text("ACHAT" if buying else "VENTE", style="cyan" if buying else "green"),
                        f"{tx.energy_kwh:.2f}", signed(-tx.total_chf if buying else tx.total_chf))
    if not recent:
        history.add_row("—", "—", "Aucune transaction", "—", "—")
    footer = Text(
        f"Cumul de la période : {step.purchased_total_kwh:.2f} kWh achetés  ·  "
        f"{step.sold_total_kwh:.2f} kWh vendus  ·  {step.losses_total_kwh:.3f} kWh de pertes",
        style="dim")
    if compact:
        compact_finance = Text(f"Prix {step.price_chf_kwh:.4f} CHF/kWh  ·  Cash {money(step.cash_chf)}\n")
        compact_finance.append("Marge d’arbitrage : ")
        compact_finance.append(signed(step.trading_pnl_chf))
        return Group(header, compact_finance,
                     Panel(batteries, title="PARC DE BATTERIES", border_style="green"),
                     history, footer)
    return Group(header, top, Panel(batteries, title="PARC DE BATTERIES", border_style="green"),
                 Panel(history, title="5 DERNIÈRES TRANSACTIONS", border_style="blue"), footer)


def build_final_report(company: Company, result: SimulationResult) -> Group:
    efficiency = result.round_trip_efficiency
    efficiency_label = f"{efficiency:.2%}" if efficiency is not None else "N/D · stock initial ou final non nul"
    return Group(
        metrics([
            ("Période simulée", f"{result.simulated_days:g} jours · {len(result.steps)} pas"),
            ("Capital initial", money(result.initial_capital_chf)),
            ("Investissement batteries", money(company.battery_purchase_cost)),
            ("Achats d’énergie", money(company.total_energy_cost)),
            ("Ventes d’énergie", money(company.total_revenue)),
            ("Marge d’arbitrage", signed(company.trading_pnl())),
            ("Maintenance", money(company.maintenance_cost)),
            ("Solde après investissement et maintenance", signed(company.net_profit())),
            ("Trésorerie finale", money(company.cash_chf)),
        ], "BILAN FINANCIER", "magenta"),
        metrics([
            ("Stock initial → final", f"{sum(result.initial_soc_kwh.values()):.3f} → {result.soc_kwh[-1]:.3f} kWh"),
            ("Énergie achetée / vendue", f"{result.purchased_kwh:.3f} / {result.sold_kwh:.3f} kWh"),
            ("Pertes de conversion", f"{result.conversion_losses_kwh:.4f} kWh"),
            ("Pertes dues à la dégradation", f"{result.degradation_losses_kwh:.4f} kWh"),
            ("Rendement observé · stock vide → vide", efficiency_label),
            ("Écart du bilan énergétique", f"{result.energy_balance_error_kwh:.8f} kWh"),
        ], "BILAN ÉNERGÉTIQUE", "green"),
        Text("Modèle simplifié : valeur résiduelle des batteries et du stock non valorisée.\n"
             "Les frais réseau, taxes et coûts fixes ne sont pas simulés.", style="dim"),
    )


class LiveCockpit:
    def __init__(self, output: Console = console, *, delay: float = 0.0,
                 live: bool = True, verbose: bool = False) -> None:
        self.console = output
        self.delay = delay
        self.verbose = verbose
        self.enabled = live and output.is_terminal and not verbose
        self.recent: deque[Transaction] = deque(maxlen=5)
        self.last_step: StepResult | None = None
        self._live: Live | None = None
        self._last_refresh = 0.0

    def __enter__(self) -> "LiveCockpit":
        if self.enabled:
            self._live = Live(console=self.console, auto_refresh=False, transient=True)
            self._live.__enter__()
        return self

    def on_step(self, step: StepResult) -> None:
        self.last_step = step
        self.recent.extendleft(step.transactions)
        now = monotonic()
        if self.verbose or (self._live and (now - self._last_refresh >= 0.1 or step.step_index + 1 == step.total_steps)):
            view = build_dashboard(step, self.recent, width=self.console.width,
                                   compact=bool(self._live) and self.console.height < 38)
            if self.verbose:
                self.console.print(view)
            elif self._live:
                self._live.update(view, refresh=True)
            self._last_refresh = now
        if self.enabled and self.delay:
            sleep(self.delay)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._live:
            self._live.__exit__(exc_type, exc_value, traceback)
        if exc_type is None and self.last_step and not self.verbose:
            self.console.print(build_dashboard(self.last_step, self.recent, width=self.console.width))
