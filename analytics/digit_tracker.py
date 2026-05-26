"""
analytics/digit_tracker.py — Tracks digit history and computes statistics.
Used by market_filter and volatility_selector for scoring.
"""

import collections
import logging
from dataclasses import dataclass, field
from typing import Deque

import numpy as np

import config

logger = logging.getLogger(__name__)


@dataclass
class DigitStats:
    """Summary statistics for a single symbol's digit stream."""
    symbol: str
    total_ticks: int = 0
    digit_counts: dict = field(default_factory=lambda: {i: 0 for i in range(10)})
    over3_rate: float = 0.0        # empirical win rate (digits 4-9)
    stability_score: float = 0.0   # 0–1, higher = more stable
    spike_count: int = 0
    momentum: float = 0.0          # rolling directional bias
    market_score: float = 0.0      # composite 0–1


class DigitTracker:
    """
    Maintains a rolling window of raw prices and last digits per symbol.
    Computes all statistics needed for market scoring.
    """

    def __init__(self):
        # Rolling deque of raw prices per symbol
        self._prices: dict[str, Deque[float]] = {}
        # Rolling deque of extracted last-digits per symbol
        self._digits: dict[str, Deque[int]] = {}

    def _ensure_symbol(self, symbol: str) -> None:
        if symbol not in self._prices:
            self._prices[symbol] = collections.deque(maxlen=config.TICK_HISTORY_SIZE)
            self._digits[symbol] = collections.deque(maxlen=config.TICK_HISTORY_SIZE)

    def add_tick(self, symbol: str, price: float) -> None:
        """Record one incoming tick price."""
        self._ensure_symbol(symbol)
        self._prices[symbol].append(price)
        digit = int(str(price).replace(".", "")[-1])
        self._digits[symbol].append(digit)

    def add_history(self, symbol: str, prices: list[float]) -> None:
        """Bulk-load historical prices (e.g. from ticks_history API)."""
        for p in prices:
            self.add_tick(symbol, float(p))

    # ─── Statistics ──────────────────────────────────────────────────────────

    def digit_distribution(self, symbol: str, window: int | None = None) -> dict[int, float]:
        """
        Return fractional frequency of each digit 0-9
        over the last `window` ticks (default: ANALYSIS_WINDOW).
        """
        digits = list(self._digits.get(symbol, []))
        if window:
            digits = digits[-window:]
        if not digits:
            return {i: 0.1 for i in range(10)}
        n = len(digits)
        return {i: digits.count(i) / n for i in range(10)}

    def over3_empirical_rate(self, symbol: str, window: int | None = None) -> float:
        """Fraction of recent digits that are 4-9 (theoretical = 0.60)."""
        dist = self.digit_distribution(symbol, window or config.ANALYSIS_WINDOW)
        return sum(dist[d] for d in range(4, 10))

    def stability_score(self, symbol: str) -> float:
        """
        Score 0–1 measuring price stream stability.
        Uses z-score of tick deltas; penalises spikes and erratic jumps.
        """
        prices = np.array(list(self._prices.get(symbol, [])), dtype=float)
        if len(prices) < 20:
            return 0.5  # not enough data, neutral

        deltas = np.abs(np.diff(prices))
        mean_d = np.mean(deltas)
        std_d = np.std(deltas) + 1e-9
        z_scores = (deltas - mean_d) / std_d

        spike_count = int(np.sum(z_scores > config.SPIKE_THRESHOLD))
        spike_ratio = spike_count / len(deltas)

        # Stability is inversely proportional to spike ratio
        score = max(0.0, 1.0 - (spike_ratio * 5))
        return round(score, 4)

    def momentum(self, symbol: str, short: int = 10, long: int = 30) -> float:
        """
        Simple momentum: difference between short and long rolling digit means.
        Positive → digits trending higher recently.
        """
        digits = list(self._digits.get(symbol, []))
        if len(digits) < long:
            return 0.0
        short_mean = np.mean(digits[-short:])
        long_mean = np.mean(digits[-long:])
        return round(float(short_mean - long_mean), 4)

    def compute_stats(self, symbol: str) -> DigitStats:
        """Compute and return a full DigitStats snapshot for one symbol."""
        stats = DigitStats(symbol=symbol)
        digits = list(self._digits.get(symbol, []))
        stats.total_ticks = len(digits)

        if not digits:
            return stats

        dist = self.digit_distribution(symbol)
        stats.digit_counts = {d: int(dist[d] * len(digits)) for d in range(10)}
        stats.over3_rate = self.over3_empirical_rate(symbol)
        stats.stability_score = self.stability_score(symbol)
        stats.spike_count = sum(
            1 for d in list(self._prices.get(symbol, []))
            if False  # spike_count is embedded in stability_score
        )
        stats.momentum = self.momentum(symbol)
        stats.market_score = self._composite_score(stats)
        return stats

    def _composite_score(self, stats: DigitStats) -> float:
        """
        Weighted composite market quality score 0–1.

        Weights:
          - over3_rate:       40%  (empirical edge)
          - stability_score:  35%  (stream quality)
          - momentum_factor:  25%  (short-term bias)
        """
        # Normalise over3_rate around theoretical 0.60
        # Anything above 0.58 gets a positive weight
        over3_norm = min(stats.over3_rate / 0.60, 1.0)

        # Momentum: slight upward bias preferred (digits > 3 trending up)
        momentum_norm = min(max((stats.momentum + 2) / 4, 0.0), 1.0)

        score = (
            0.40 * over3_norm +
            0.35 * stats.stability_score +
            0.25 * momentum_norm
        )
        return round(score, 4)
