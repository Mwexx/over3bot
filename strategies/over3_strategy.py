"""
strategies/over3_strategy.py — Core trading loop for DIGIT OVER 3.

Orchestrates:
  - market selection & re-scoring
  - market filter evaluation
  - stake computation via martingale
  - trade execution & result handling
  - cooldown & reconnection
"""

import asyncio
import logging
import time

from analytics.digit_tracker import DigitTracker
from analytics.logs import log_trade
from api.deriv_client import DerivClient
from risk.bankroll import BankrollManager
from risk.martingale import MartingaleManager
from strategies.market_filter import MarketFilter
from strategies.volatility_selector import VolatilitySelector
import config

logger = logging.getLogger(__name__)


class Over3Strategy:
    """
    Main strategy loop.

    Call `await strategy.run()` to start.
    Set `strategy.running = False` to stop gracefully.
    """

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
        self.running = False
        self._active_symbol = config.DEFAULT_SYMBOL
        self._last_rescan: float = 0.0
        self._rescan_interval: float = 60.0  # rescan markets every 60s
        self._duplicate_guard: set[int] = set()

    async def run(self) -> str:
        """
        Main loop. Returns a stop-reason string when it exits.
        """
        self.running = True
        logger.info("Strategy started.")
        self._log("Strategy started. Scanning markets…")

        # Initial market scan
        await self._rescan_markets()

        # Subscribe to live ticks for the selected symbol
        await self._subscribe_active_symbol()

        while self.running:
            # ── Check global stop conditions ──────────────────────────────
            should_stop, reason = self.bankroll.should_stop()
            if should_stop:
                logger.warning("BOT STOPPING: %s", reason)
                self._log(f"[bold red]STOP: {reason}[/bold red]")
                self.running = False
                return reason

            # ── Periodic market rescan ─────────────────────────────────────
            if time.time() - self._last_rescan > self._rescan_interval:
                await self._rescan_markets()
                await self._subscribe_active_symbol()

            # ── Evaluate market conditions ─────────────────────────────────
            stats = self.tracker.compute_stats(self._active_symbol)
            can_trade, filter_reason = self.market_filter.evaluate(
                stats, self.bankroll.consecutive_losses
            )

            self._push_dashboard(stats, can_trade, filter_reason)

            if not can_trade:
                logger.debug("Filter blocked trade: %s", filter_reason)
                await asyncio.sleep(2.0)
                continue

            # ── Place trade ────────────────────────────────────────────────
            stake = self.martingale.current_stake()
            await self._execute_trade(stake, stats)

            # ── Cooldown after consecutive losses ─────────────────────────
            if self.bankroll.consecutive_losses >= 2:
                cd = config.COOLDOWN_SECONDS
                logger.info("Cooling down %.1fs after %d losses.", cd, self.bankroll.consecutive_losses)
                self._log(f"Cooldown {cd}s after {self.bankroll.consecutive_losses} losses.")
                await asyncio.sleep(cd)
            else:
                await asyncio.sleep(0.5)  # brief pause between trades

        return "manual_stop"

    # ─── Trade execution ─────────────────────────────────────────────────────

    async def _execute_trade(self, stake: float, stats) -> None:
        symbol = self._active_symbol
        logger.info(
            "Placing OVER3 | %s | stake=%.2f | mstep=%d",
            symbol, stake, self.martingale.step,
        )
        self._log(f"Trade → {symbol} stake={stake:.2f} step={self.martingale.step}")

        try:
            buy_resp = await self.client.buy_over3(symbol, stake)
            contract_id: int = buy_resp["buy"]["contract_id"]

            # Duplicate guard
            if contract_id in self._duplicate_guard:
                logger.warning("Duplicate contract_id %d — skipping.", contract_id)
                return
            self._duplicate_guard.add(contract_id)
            # Keep set bounded
            if len(self._duplicate_guard) > 500:
                self._duplicate_guard = set(list(self._duplicate_guard)[-200:])

            # Wait for settlement
            result = await self.client.wait_for_contract_result(contract_id)
            self._process_result(result, symbol, stake, stats)

        except Exception as e:
            logger.error("Trade execution error: %s", e, exc_info=True)
            self._log(f"[red]Trade error: {e}[/red]")

    def _process_result(self, result: dict, symbol: str, stake: float, stats) -> None:
        profit = float(result.get("profit", 0.0))
        is_won = profit > 0
        exit_tick = result.get("exit_tick_display_value", "")
        last_digit = int(str(exit_tick).replace(".", "")[-1]) if exit_tick else None

        # Refresh balance
        balance = self.client.balance

        if is_won:
            self.bankroll.record_win(profit)
            self.martingale.on_win()
            self._log(f"[green]WIN +{profit:.2f}[/green] digit={last_digit} | PnL={self.bankroll.session_pnl:+.2f}")
        else:
            loss_amt = abs(profit) if profit < 0 else stake
            self.bankroll.record_loss(loss_amt)
            self.martingale.on_loss()
            self._log(f"[red]LOSS -{loss_amt:.2f}[/red] digit={last_digit} | PnL={self.bankroll.session_pnl:+.2f}")

        # Persist to DB
        log_trade(
            symbol=symbol,
            stake=stake,
            last_digit=last_digit,
            result="win" if is_won else "loss",
            pnl=profit,
            balance=balance,
            market_score=stats.market_score,
            martingale_step=self.martingale.step,
        )

    # ─── Market management ───────────────────────────────────────────────────

    async def _rescan_markets(self) -> None:
        logger.info("Rescanning volatility indices…")
        stats_map = await self.selector.scan_all()
        scores = {sym: st.market_score for sym, st in stats_map.items()}

        new_symbol = self.selector.best_symbol(stats_map)
        if new_symbol != self._active_symbol:
            logger.info("Switching active symbol: %s → %s", self._active_symbol, new_symbol)
            self._log(f"Market switch: {self._active_symbol} → {new_symbol}")
            self._active_symbol = new_symbol

        self._last_rescan = time.time()
        if self.dashboard:
            self.dashboard.update({"market_scores": scores})

    async def _subscribe_active_symbol(self) -> None:
        """Subscribe tracker callback to live ticks."""
        self.client.on_tick(
            self._active_symbol,
            self._on_tick,
        )
        await self.client.subscribe_ticks(self._active_symbol)

    async def _on_tick(self, tick: dict) -> None:
        """Handle an incoming live tick."""
        price = float(tick.get("quote", 0))
        self.tracker.add_tick(self._active_symbol, price)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        if self.dashboard:
            self.dashboard.add_log(msg)

    def _push_dashboard(self, stats, can_trade: bool, filter_reason: str) -> None:
        if not self.dashboard:
            return
        summary = self.bankroll.summary()
        self.dashboard.update({
            "running": self.running,
            "active_symbol": self._active_symbol,
            "balance": self.client.balance,
            "session_pnl": summary["session_pnl"],
            "total_trades": summary["total_trades"],
            "wins": summary["wins"],
            "losses": summary["losses"],
            "win_rate": summary["win_rate"],
            "consecutive_losses": summary["consecutive_losses"],
            "consecutive_wins": summary["consecutive_wins"],
            "current_stake": self.martingale.current_stake(),
            "martingale_step": self.martingale.step,
            "over3_rate": stats.over3_rate,
            "stability_score": stats.stability_score,
            "momentum": stats.momentum,
            "market_score": stats.market_score,
            "last_digit": None,
            "filter_reason": filter_reason if not can_trade else "✓ Clear",
        })
