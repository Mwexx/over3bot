"""
strategies/market_filter.py — Gate that decides whether conditions are
good enough to place a trade right now.
"""

import logging

from analytics.digit_tracker import DigitStats
import config

logger = logging.getLogger(__name__)


class MarketFilter:
    """
    Evaluates real-time stats and returns (should_trade: bool, reason: str).
    All filters must pass before the bot places a trade.
    """

    def evaluate(self, stats: DigitStats, consecutive_losses: int) -> tuple[bool, str]:
        """
        Returns (True, "OK") if all conditions are met,
        otherwise (False, <reason_string>).
        """

        # Filter 1 — Minimum market score
        if stats.market_score < config.MIN_MARKET_SCORE:
            return False, f"Low market score ({stats.market_score:.3f} < {config.MIN_MARKET_SCORE})"

        # Filter 2 — Stability check
        if stats.stability_score < 0.4:
            return False, f"Unstable market (stability={stats.stability_score:.3f})"

        # Filter 3 — Sufficient tick data
        if stats.total_ticks < 50:
            return False, f"Insufficient tick data ({stats.total_ticks} ticks)"

        # Filter 4 — Consecutive loss protection
        if consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            return False, f"Consecutive loss limit reached ({consecutive_losses})"

        # Filter 5 — Over-3 empirical rate must be at least neutral
        if stats.over3_rate < 0.52:
            return False, f"Low empirical over-3 rate ({stats.over3_rate:.2%})"

        return True, "OK"
