"""Market gate that decides whether conditions are tradeable."""

from __future__ import annotations

from analytics.digit_tracker import DigitStats
import config


class MarketFilter:
    """All filters must pass before the bot places a trade."""

    def evaluate(self, stats: DigitStats, consecutive_losses: int, latency_ms: float = 0.0) -> tuple[bool, str]:
        if stats.total_ticks < config.MIN_TICKS_TO_TRADE:
            return False, f"Insufficient tick data ({stats.total_ticks} ticks)"
        if stats.market_score < config.MIN_MARKET_SCORE:
            return False, f"Low market score ({stats.market_score:.3f} < {config.MIN_MARKET_SCORE})"
        if stats.stability_score < config.MIN_STABILITY_SCORE:
            return False, f"Unstable market (stability={stats.stability_score:.3f})"
        if stats.spike_ratio > config.MAX_SPIKE_RATIO:
            return False, f"Spike ratio too high ({stats.spike_ratio:.2%})"
        if consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            return False, f"Consecutive loss limit reached ({consecutive_losses})"
        if stats.over3_rate < config.MIN_OVER3_RATE:
            return False, f"Low empirical over-3 rate ({stats.over3_rate:.2%})"
        if latency_ms and latency_ms > config.MAX_LATENCY_MS:
            return False, f"High API latency ({latency_ms:.0f} ms)"
        return True, "OK"
