"""Tracks session PnL and enforces stop rules."""

from __future__ import annotations

import logging

from risk.stoploss import StopRules

logger = logging.getLogger(__name__)


class BankrollManager:
    """Tracks session PnL, wins/losses, and risk-stop state."""

    def __init__(self, starting_balance: float, stop_rules: StopRules | None = None):
        self.starting_balance = starting_balance
        self.stop_rules = stop_rules or StopRules()
        self.session_pnl = 0.0
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0

    def record_win(self, profit: float) -> None:
        self.session_pnl += profit
        self.gross_profit += profit
        self.consecutive_losses = 0
        self.consecutive_wins += 1
        self.wins += 1
        self.total_trades += 1
        logger.info("WIN +%.2f | Session PnL: %.2f", profit, self.session_pnl)

    def record_loss(self, loss: float) -> None:
        """Record a loss as a positive amount."""
        self.session_pnl -= loss
        self.gross_loss += loss
        self.consecutive_wins = 0
        self.consecutive_losses += 1
        self.losses += 1
        self.total_trades += 1
        logger.info("LOSS -%.2f | Session PnL: %.2f", loss, self.session_pnl)

    def should_stop(self) -> tuple[bool, str]:
        """Return (True, reason) if the bot must stop."""
        return self.stop_rules.evaluate(self.session_pnl, self.total_trades)

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_trades if self.total_trades else 0.0

    def summary(self) -> dict:
        return {
            "session_pnl": round(self.session_pnl, 2),
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate * 100, 1),
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "avg_profit": round(self.gross_profit / self.wins, 2) if self.wins else 0.0,
            "avg_loss": round(self.gross_loss / self.losses, 2) if self.losses else 0.0,
        }
