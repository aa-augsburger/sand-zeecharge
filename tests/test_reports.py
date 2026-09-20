from collections import deque
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest
from rich.console import Console

from models.company import Company
from reports.report import export_results, save_html_report
from simulation.engine import SimulationEngine
from simulation.market import EnergyMarket
from strategies.threshold import ThresholdStrategy
from ui.console import LiveCockpit, build_dashboard, build_final_report


@pytest.fixture
def completed(battery_factory):
    company = Company(100, [battery_factory(charge_efficiency=.95, discharge_efficiency=.95)])
    market = EnergyMarket(pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=3, freq="h"),
                                        "price_chf_kwh": [.05, .25, .12]}))
    result = SimulationEngine().run(market, company, ThresholdStrategy())
    return company, result


@pytest.mark.parametrize("width", [60, 80, 120])
def test_rich_rendering_and_idle_history(completed, width):
    company, result = completed
    stream = io.StringIO()
    output = Console(file=stream, width=width, color_system=None, legacy_windows=False)
    with LiveCockpit(output, live=False) as cockpit:
        for step in result.steps:
            cockpit.on_step(step)
    assert len(cockpit.recent) == 2
    output.print(build_final_report(company, result))
    rendered = stream.getvalue()
    assert "B001" in rendered
    assert "90.25%" in rendered
    assert "46.28%" not in rendered
    assert "SAND ZEECHARGE" in rendered
    assert all(len(line) <= width for line in rendered.splitlines())


def test_compact_dashboard_fits_standard_terminal(completed):
    _, result = completed
    stream = io.StringIO()
    output = Console(file=stream, width=80, color_system=None, legacy_windows=False)
    output.print(build_dashboard(result.steps[-1], deque(result.steps[0].transactions), width=80, compact=True))
    assert len(stream.getvalue().splitlines()) <= 24


def test_live_console_path(completed):
    _, result = completed
    stream = io.StringIO()
    output = Console(file=stream, width=100, height=24, force_terminal=True, legacy_windows=False)
    with LiveCockpit(output, live=True, delay=0) as cockpit:
        for step in result.steps:
            cockpit.on_step(step)
    assert "SAND ZEECHARGE" in stream.getvalue()
    assert len(cockpit.recent) == 2


def test_machine_readable_and_html_reports(completed, tmp_path):
    company, result = completed
    export_results(company, result, tmp_path)
    save_html_report(company, result, tmp_path / "report.html")
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["observed_round_trip_efficiency"] == pytest.approx(.9025)
    assert summary["energy_balance_error_kwh"] == pytest.approx(0, abs=1e-9)
    assert len(pd.read_csv(tmp_path / "transactions.csv")) == 2
    assert len(pd.read_csv(tmp_path / "steps.csv")) == 3
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "90.25%" in html
    assert "B001" in html


def test_cli_from_another_directory_and_windows_legacy_encoding(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    # The application explicitly configures UTF-8 on Windows.
    if sys.platform != "win32":
        env["PYTHONIOENCODING"] = "utf-8"
    run = subprocess.run([sys.executable, str(root / "main.py"), "--days", "1", "--no-live",
                          "--no-plots", "--output", str(tmp_path / "output")], cwd=tmp_path,
                         env=env, capture_output=True, encoding="utf-8", check=False)
    assert run.returncode == 0, run.stderr
    assert "BILAN FINANCIER" in run.stdout
    assert (tmp_path / "output" / "report.html").exists()


def test_cli_reports_invalid_input_without_traceback(tmp_path):
    root = Path(__file__).resolve().parents[1]
    run = subprocess.run([sys.executable, str(root / "main.py"), "--efficiency", "2", "--no-live"],
                         cwd=tmp_path, capture_output=True, encoding="utf-8", check=False)
    assert run.returncode == 2
    assert "Traceback" not in run.stderr + run.stdout
    assert "Erreur" in run.stdout
