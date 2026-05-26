"""Rich terminal dashboard for the bot."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config

console = Console()


class TerminalDashboard:
    """Live terminal dashboard updated in a background task."""

    def __init__(self):
        self._state: dict = {}
        self._live: Live | None = None
        self._task: asyncio.Task | None = None
        self._running = False
        self._log_lines: list[str] = []

    def update(self, state: dict) -> None:
        self._state.update(state)

    def add_log(self, line: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._log_lines.append(f"[dim]{timestamp}[/dim] {line}")
        self._log_lines = self._log_lines[-12:]

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._render_loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        if self._live:
            self._live.stop()

    async def _render_loop(self) -> None:
        refresh = max(int(1 / config.DASHBOARD_REFRESH_RATE), 1)
        with Live(self._build_layout(), console=console, refresh_per_second=refresh, screen=True) as live:
            self._live = live
            while self._running:
                live.update(self._build_layout())
                await asyncio.sleep(config.DASHBOARD_REFRESH_RATE)

    def _build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=14))
        layout["body"].split_row(Layout(name="stats", ratio=1), Layout(name="market", ratio=1))
        layout["header"].update(self._header())
        layout["stats"].update(self._stats_panel())
        layout["market"].update(self._market_panel())
        layout["footer"].update(self._log_panel())
        return layout

    def _header(self) -> Panel:
        state = self._state
        status_color = "green" if state.get("running") else "red"
        status_text = "RUNNING" if state.get("running") else "STOPPED"
        title = Text()
        title.append(" DERIV OVER 3 BOT ", style="bold white on dark_blue")
        title.append(f" {status_text}", style=f"bold {status_color}")
        title.append(f" {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", style="dim")
        return Panel(title, style="bold")

    def _stats_panel(self) -> Panel:
        state = self._state
        table = Table.grid(expand=True)
        table.add_column(style="dim", width=22)
        table.add_column(style="bold")

        pnl = state.get("session_pnl", 0.0)
        pnl_color = "green" if pnl >= 0 else "red"
        rows = [
            ("Session PnL", f"[{pnl_color}]{pnl:+.2f} USD[/{pnl_color}]"),
            ("Balance", f"{state.get('balance', 0.0):.2f} USD"),
            ("Total Trades", str(state.get("total_trades", 0))),
            ("Win Rate", f"{state.get('win_rate', 0.0):.1f}%"),
            ("Recent Win Rate", f"{state.get('recent_win_rate', 0.0):.1f}%"),
            ("Wins / Losses", f"[green]{state.get('wins', 0)}[/green] / [red]{state.get('losses', 0)}[/red]"),
            ("Avg Win / Loss", f"{state.get('avg_profit', 0.0):.2f} / {state.get('avg_loss', 0.0):.2f}"),
            ("Consec. Losses", f"[red]{state.get('consecutive_losses', 0)}[/red]"),
            ("Consec. Wins", f"[green]{state.get('consecutive_wins', 0)}[/green]"),
            ("Current Stake", f"{state.get('current_stake', 0.0):.2f} USD"),
            ("Martingale Step", str(state.get("martingale_step", 0))),
            ("Stop / Target", f"{config.STOP_LOSS:.2f} / {config.TAKE_PROFIT:.2f}"),
        ]
        for label, value in rows:
            table.add_row(label, value)
        return Panel(table, title="[bold]Session Stats[/bold]", border_style="blue")

    def _market_panel(self) -> Panel:
        state = self._state
        table = Table.grid(expand=True)
        table.add_column(style="dim", width=14)
        table.add_column()

        rows = [
            ("Symbol", state.get("active_symbol", "-")),
            ("Last Digit", str(state.get("last_digit", "-"))),
            ("Over3 Rate", f"{state.get('over3_rate', 0.0):.1%}"),
            ("Stability", f"{state.get('stability_score', 0.0):.3f}"),
            ("Spike Ratio", f"{state.get('spike_ratio', 0.0):.2%}"),
            ("Momentum", f"{state.get('momentum', 0.0):+.3f}"),
            ("Tick Speed", f"{state.get('tick_speed', 0.0):.2f}/s"),
            ("Mkt Score", f"{state.get('market_score', 0.0):.3f}"),
            ("API Latency", f"{state.get('latency_ms', 0.0):.0f} ms"),
            ("Avg Latency", f"{state.get('avg_latency_ms', 0.0):.0f} ms"),
            ("Avg Exec", f"{state.get('avg_execution_ms', 0.0):.0f} ms"),
            ("Best / Worst", f"{state.get('best_market', '-')} / {state.get('worst_market', '-')}"),
            ("Filter", state.get("filter_reason", "-")),
        ]
        for label, value in rows:
            table.add_row(label, value)

        market_scores = state.get("market_scores", {})
        if market_scores:
            table.add_row("", "")
            table.add_row("[bold]Symbol[/bold]", "[bold]Score[/bold]")
            for symbol, score in sorted(market_scores.items(), key=lambda item: -item[1]):
                bar = "#" * int(score * 20)
                color = "green" if score >= config.MIN_MARKET_SCORE else "red"
                table.add_row(symbol, f"[{color}]{score:.3f} {bar}[/{color}]")

        return Panel(table, title="[bold]Market Analysis[/bold]", border_style="cyan")

    def _log_panel(self) -> Panel:
        text = Text()
        for line in self._log_lines:
            text.append(line + "\n")
        return Panel(text, title="[bold]Activity Log[/bold]", border_style="dark_orange")
