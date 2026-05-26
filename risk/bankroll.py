"""
risk/bankroll.py — Tracks session PnL and enforces stop-loss / take-profit.
"""

import logging
import config

logger = logging.getLogger(__name__)


class BankrollManager:
    """
    Tracks:
      - session_pnl (net profit/loss since bot started)
      - consecutive_losses
      - consecutive_wins
      - total_trades (today)
      - starting_balance
    """

    def __init__(self, starting_balance: float):
        self.starting_balance = starting_balance
        self.session_pnl: float = 0.0
        self.consecutive_losses: int = 0
        self.consecutive_wins: int = 0
        self.total_trades: int = 0
        self.wins: int = 0
        self.losses: int = 0

    # ─── Trade recording ─────────────────────────────────────────────────────

    def record_win(self, profit: float) -> None:
        self.session_pnl += profit
        self.consecutive_losses = 0
        self.consecutive_wins += 1
        self.wins += 1
        self.total_trades += 1
        logger.info("WIN +%.2f | Session PnL: %.2f", profit, self.session_pnl)

    def record_loss(self, loss: float) -> None:
        """loss should be a positive number representing amount lost."""
        self.session_pnl -= loss
        self.consecutive_wins = 0
        self.consecutive_losses += 1
        self.losses += 1
        self.total_trades += 1
        logger.info("LOSS -%.2f | Session PnL: %.2f", loss, self.session_pnl)

    # ─── Checks ──────────────────────────────────────────────────────────────

    def should_stop(self) -> tuple[bool, str]:
        """Return (True, reason) if bot must stop, else (False, '')."""
        if self.session_pnl <= config.STOP_LOSS:
            return True, f"Stop-loss triggered (PnL={self.session_pnl:.2f})"
        if self.session_pnl >= config.TAKE_PROFIT:
            return True, f"Take-profit reached (PnL={self.session_pnl:.2f})"
        if self.total_trades >= config.MAX_DAILY_TRADES:
            return True, f"Max daily trades reached ({self.total_trades})"
        return False, ""

    # ─── Stats ───────────────────────────────────────────────────────────────

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades

    def summary(self) -> dict:
        return {
            "session_pnl": round(self.session_pnl, 2),
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate * 100, 1),
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
        }
