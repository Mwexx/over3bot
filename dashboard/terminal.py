"""
dashboard/terminal.py — Live Rich terminal dashboard for the bot.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config

logger = logging.getLogger(__name__)
console = Console()


class TerminalDashboard:
    """
    Renders a live terminal dashboard updated every DASHBOARD_REFRESH_RATE seconds.

    Usage:
        dash = TerminalDashboard()
        await dash.start()     # runs in background
        dash.update(state)     # call from main loop
        dash.stop()
    """

    def __init__(self):
        self._state: dict = {}
        self._live: Live | None = None
        self._task: asyncio.Task | None = None
        self._running = False
        self._log_lines: list[str] = []

    def update(self, state: dict) -> None:
        """Push new state snapshot (non-blocking)."""
        self._state = state

    def add_log(self, line: str) -> None:
        """Append a log line shown in the dashboard."""
        ts = datetime.utcnow().strftime("%H:%M:%S")
        self._log_lines.append(f"[dim]{ts}[/dim] {line}")
        if len(self._log_lines) > 12:
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

    # ─── Rendering ───────────────────────────────────────────────────────────

    async def _render_loop(self) -> None:
        with Live(
            self._build_layout(),
            console=console,
            refresh_per_second=int(1 / config.DASHBOARD_REFRESH_RATE),
            screen=True,
        ) as live:
            self._live = live
            while self._running:
                live.update(self._build_layout())
                await asyncio.sleep(config.DASHBOARD_REFRESH_RATE)

    def _build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=14),
        )
        layout["body"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="market", ratio=1),
        )

        layout["header"].update(self._header())
        layout["stats"].update(self._stats_panel())
        layout["market"].update(self._market_panel())
        layout["footer"].update(self._log_panel())

        return layout

    def _header(self) -> Panel:
        s = self._state
        status_color = "green" if s.get("running") else "red"
        status_text = "● RUNNING" if s.get("running") else "■ STOPPED"
        title = Text()
        title.append("  DERIV OVER 3 BOT  ", style="bold white on dark_blue")
        title.append(f"  {status_text}", style=f"bold {status_color}")
        title.append(
            f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            style="dim",
        )
        return Panel(title, style="bold")

    def _stats_panel(self) -> Panel:
        s = self._state
        table = Table.grid(expand=True)
        table.add_column(style="dim", width=22)
        table.add_column(style="bold")

        pnl = s.get("session_pnl", 0.0)
        pnl_color = "green" if pnl >= 0 else "red"

        rows = [
            ("Session PnL",        f"[{pnl_color}]{pnl:+.2f} USD[/{pnl_color}]"),
            ("Balance",            f"{s.get('balance', 0.0):.2f} USD"),
            ("Total Trades",       str(s.get("total_trades", 0))),
            ("Win Rate",           f"{s.get('win_rate', 0.0):.1f}%"),
            ("Wins / Losses",      f"[green]{s.get('wins',0)}[/green] / [red]{s.get('losses',0)}[/red]"),
            ("Consec. Losses",     f"[red]{s.get('consecutive_losses', 0)}[/red]"),
            ("Consec. Wins",       f"[green]{s.get('consecutive_wins', 0)}[/green]"),
            ("Current Stake",      f"{s.get('current_stake', 0.0):.2f} USD"),
            ("Martingale Step",    str(s.get("martingale_step", 0))),
            ("Stop Loss",          f"{config.STOP_LOSS:.2f}"),
            ("Take Profit",        f"{config.TAKE_PROFIT:.2f}"),
        ]

        for label, value in rows:
            table.add_row(label, value)

        return Panel(table, title="[bold]Session Stats[/bold]", border_style="blue")

    def _market_panel(self) -> Panel:
        s = self._state
        table = Table.grid(expand=True)
        table.add_column(style="dim", width=10)
        table.add_column()

        market_data = s.get("market_scores", {})

        rows = [
            ("Symbol",       s.get("active_symbol", "—")),
            ("Last Digit",   str(s.get("last_digit", "—"))),
            ("Over3 Rate",   f"{s.get('over3_rate', 0.0):.1%}"),
            ("Stability",    f"{s.get('stability_score', 0.0):.3f}"),
            ("Momentum",     f"{s.get('momentum', 0.0):+.3f}"),
            ("Mkt Score",    f"{s.get('market_score', 0.0):.3f}"),
            ("Filter",       s.get("filter_reason", "—")),
        ]
        for label, value in rows:
            table.add_row(label, value)

        # Market ranking mini-table
        if market_data:
            table.add_row("", "")
            table.add_row("[bold]Symbol[/bold]", "[bold]Score[/bold]")
            for sym, score in sorted(market_data.items(), key=lambda x: -x[1]):
                bar = "█" * int(score * 20)
                color = "green" if score >= config.MIN_MARKET_SCORE else "red"
                table.add_row(sym, f"[{color}]{score:.3f} {bar}[/{color}]")

        return Panel(table, title="[bold]Market Analysis[/bold]", border_style="cyan")

    def _log_panel(self) -> Panel:
        log_text = Text()
        for line in self._log_lines:
            log_text.append(line + "\n")
        return Panel(log_text, title="[bold]Activity Log[/bold]", border_style="dark_orange")
