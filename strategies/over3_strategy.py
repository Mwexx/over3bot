"""Core trading loop for DIGIT OVER 3."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from analytics.digit_tracker import DigitStats, DigitTracker
from analytics.logs import log_trade
from analytics.performance import PerformanceTracker
from api.deriv_client import DerivClient
from risk.bankroll import BankrollManager
from risk.martingale import MartingaleManager
from strategies.market_filter import MarketFilter
from strategies.volatility_selector import VolatilitySelector
import config

logger = logging.getLogger(__name__)


class Over3Strategy:
    """Selective DIGITOVER 3 strategy with dynamic market selection."""

    def __init__(
        self,
        client: DerivClient,
        tracker: DigitTracker,
        bankroll: BankrollManager,
        dashboard=None,
    ):
        self.client = client
        self.tracker = tracker
        self.bankroll = bankroll
        self.dashboard = dashboard
        self.martingale = MartingaleManager()
        self.market_filter = MarketFilter()
        self.selector = VolatilitySelector(client, tracker)
        self.performance = PerformanceTracker()
        self.running = False
        self._active_symbol = config.DEFAULT_SYMBOL
        self._subscribed_symbol: str | None = None
        self._last_rescan = 0.0
        self._duplicate_guard: set[int] = set()
        self._market_scores: dict[str, float] = {}

    async def run(self) -> str:
        """Run until stopped and return the stop reason."""
        self.running = True
        logger.info("Strategy started.")
        self._log("Strategy started. Scanning markets.")

        await self._rescan_markets()
        await self._subscribe_active_symbol()

        while self.running:
            should_stop, reason = self.bankroll.should_stop()
            if should_stop:
                logger.warning("BOT STOPPING: %s", reason)
                self._log(f"[bold red]STOP: {reason}[/bold red]")
                self.running = False
                return reason

            if time.time() - self._last_rescan > config.MARKET_RESCAN_SECONDS:
                await self._rescan_markets()
                await self._subscribe_active_symbol()

            stats = self.tracker.compute_stats(self._active_symbol)
            can_trade, filter_reason = self.market_filter.evaluate(
                stats,
                self.bankroll.consecutive_losses,
                self.client.last_latency_ms,
            )
            self._push_dashboard(stats, can_trade, filter_reason)

            if not can_trade:
                logger.debug("Filter blocked trade: %s", filter_reason)
                await asyncio.sleep(2.0)
                continue

            stake = self.martingale.current_stake()
            await self._execute_trade(stake, stats)

            if self.bankroll.consecutive_losses >= 2:
                cooldown = config.COOLDOWN_SECONDS
                logger.info("Cooling down %.1fs after %d losses.", cooldown, self.bankroll.consecutive_losses)
                self._log(f"Cooldown {cooldown:.0f}s after {self.bankroll.consecutive_losses} losses.")
                await asyncio.sleep(cooldown)
            else:
                await asyncio.sleep(0.5)

        return "manual_stop"

    async def _execute_trade(self, stake: float, stats: DigitStats) -> None:
        symbol = self._active_symbol
        logger.info("Placing OVER3 | %s | stake=%.2f | mstep=%d", symbol, stake, self.martingale.step)
        self._log(f"Trade -> {symbol} stake={stake:.2f} step={self.martingale.step}")

        try:
            buy_response = await self.client.buy_over3(symbol, stake)
            contract_id = int(buy_response["buy"]["contract_id"])
            if contract_id in self._duplicate_guard:
                logger.warning("Duplicate contract_id %d skipped.", contract_id)
                return

            self._duplicate_guard.add(contract_id)
            if len(self._duplicate_guard) > 500:
                self._duplicate_guard = set(list(self._duplicate_guard)[-200:])

            result = await self.client.wait_for_contract_result(contract_id)
            balance = await self.client.get_balance()
            self._process_result(result, symbol, stake, stats, balance, buy_response)

        except Exception as exc:
            logger.error("Trade execution error: %s", exc, exc_info=True)
            self._log(f"[red]Trade error: {exc}[/red]")

    def _process_result(
        self,
        result: dict[str, Any],
        symbol: str,
        stake: float,
        stats: DigitStats,
        balance: float,
        buy_response: dict[str, Any],
    ) -> None:
        profit = float(result.get("profit", 0.0))
        is_won = profit > 0
        last_digit = self._last_digit_from_contract(result)
        latency_ms = float(buy_response.get("_buy_latency_ms", 0.0))
        execution_ms = float(buy_response.get("_execution_ms", 0.0))

        if is_won:
            self.bankroll.record_win(profit)
            self.martingale.on_win()
            self._log(f"[green]WIN +{profit:.2f}[/green] digit={last_digit} | PnL={self.bankroll.session_pnl:+.2f}")
        else:
            loss_amount = abs(profit) if profit < 0 else stake
            self.bankroll.record_loss(loss_amount)
            self.martingale.on_loss()
            self._log(f"[red]LOSS -{loss_amount:.2f}[/red] digit={last_digit} | PnL={self.bankroll.session_pnl:+.2f}")

        outcome = "win" if is_won else "loss"
        self.performance.record_trade(symbol, outcome, profit, latency_ms, execution_ms)
        log_trade(
            symbol=symbol,
            stake=stake,
            last_digit=last_digit,
            result=outcome,
            pnl=profit,
            balance=balance,
            market_score=stats.market_score,
            martingale_step=self.martingale.step,
            latency_ms=latency_ms,
            execution_ms=execution_ms,
            over3_rate=stats.over3_rate,
            stability_score=stats.stability_score,
            spike_ratio=stats.spike_ratio,
            momentum=stats.momentum,
        )

    @staticmethod
    def _last_digit_from_contract(result: dict[str, Any]) -> int | None:
        exit_tick = result.get("exit_tick_display_value") or result.get("exit_tick")
        if exit_tick in (None, ""):
            return None
        digits = [char for char in str(exit_tick) if char.isdigit()]
        return int(digits[-1]) if digits else None

    async def _rescan_markets(self) -> None:
        logger.info("Rescanning volatility indices.")
        stats_map = await self.selector.scan_all()
        self._market_scores = {symbol: stats.market_score for symbol, stats in stats_map.items()}

        new_symbol = self.selector.best_symbol(stats_map)
        if new_symbol != self._active_symbol:
            logger.info("Switching active symbol: %s -> %s", self._active_symbol, new_symbol)
            self._log(f"Market switch: {self._active_symbol} -> {new_symbol}")
            self._active_symbol = new_symbol

        self._last_rescan = time.time()

    async def _subscribe_active_symbol(self) -> None:
        if self._subscribed_symbol and self._subscribed_symbol != self._active_symbol:
            await self.client.unsubscribe_all_ticks()
        self.client.set_tick_callback(self._active_symbol, self._on_tick)
        await self.client.subscribe_ticks(self._active_symbol)
        self._subscribed_symbol = self._active_symbol

    async def _on_tick(self, tick: dict[str, Any]) -> None:
        symbol = str(tick.get("symbol", self._active_symbol))
        price = float(tick.get("quote", 0.0))
        epoch = tick.get("epoch")
        self.tracker.add_tick(symbol, price, float(epoch) if epoch else None)

    def _log(self, message: str) -> None:
        if self.dashboard:
            self.dashboard.add_log(message)

    def _push_dashboard(self, stats: DigitStats, can_trade: bool, filter_reason: str) -> None:
        if not self.dashboard:
            return

        summary = self.bankroll.summary()
        perf = self.performance.summary()
        self.dashboard.update(
            {
                "running": self.running,
                "active_symbol": self._active_symbol,
                "balance": self.client.balance,
                "session_pnl": summary["session_pnl"],
                "total_trades": summary["total_trades"],
                "wins": summary["wins"],
                "losses": summary["losses"],
                "win_rate": summary["win_rate"],
                "avg_profit": summary["avg_profit"],
                "avg_loss": summary["avg_loss"],
                "consecutive_losses": summary["consecutive_losses"],
                "consecutive_wins": summary["consecutive_wins"],
                "current_stake": self.martingale.current_stake(),
                "martingale_step": self.martingale.step,
                "over3_rate": stats.over3_rate,
                "stability_score": stats.stability_score,
                "spike_ratio": stats.spike_ratio,
                "momentum": stats.momentum,
                "tick_speed": stats.tick_speed,
                "market_score": stats.market_score,
                "market_scores": self._market_scores,
                "latency_ms": self.client.last_latency_ms,
                "avg_latency_ms": perf["avg_latency_ms"],
                "avg_execution_ms": perf["avg_execution_ms"],
                "recent_win_rate": perf["recent_win_rate"],
                "best_market": perf["best_market"],
                "worst_market": perf["worst_market"],
                "last_digit": None,
                "filter_reason": filter_reason if not can_trade else "Clear",
            }
        )
