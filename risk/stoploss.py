"""Stop rules for capital preservation."""

from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True)
class StopRules:
    """Session-level risk limits."""

    stop_loss: float = config.STOP_LOSS
    take_profit: float = config.TAKE_PROFIT
    max_daily_trades: int = config.MAX_DAILY_TRADES

    def evaluate(self, session_pnl: float, total_trades: int) -> tuple[bool, str]:
        if session_pnl <= self.stop_loss:
            return True, f"Stop-loss triggered (PnL={session_pnl:.2f})"
        if session_pnl >= self.take_profit:
            return True, f"Take-profit reached (PnL={session_pnl:.2f})"
        if total_trades >= self.max_daily_trades:
            return True, f"Max daily trades reached ({total_trades})"
        return False, ""
