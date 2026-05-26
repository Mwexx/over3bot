"""Digit stream tracking and market quality scoring."""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Deque

import numpy as np

import config


@dataclass
class DigitStats:
    """Snapshot of one symbol's recent tick and digit behavior."""

    symbol: str
    total_ticks: int = 0
    digit_counts: dict[int, int] = field(default_factory=lambda: {i: 0 for i in range(10)})
    over3_rate: float = 0.0
    stability_score: float = 0.0
    spike_count: int = 0
    spike_ratio: float = 0.0
    momentum: float = 0.0
    tick_speed: float = 0.0
    digit_balance_score: float = 0.0
    market_score: float = 0.0


class DigitTracker:
    """Maintains rolling prices, digits, and arrival times per symbol."""

    def __init__(self):
        self._prices: dict[str, Deque[float]] = {}
        self._digits: dict[str, Deque[int]] = {}
        self._epochs: dict[str, Deque[float]] = {}

    def _ensure_symbol(self, symbol: str) -> None:
        if symbol not in self._prices:
            self._prices[symbol] = collections.deque(maxlen=config.TICK_HISTORY_SIZE)
            self._digits[symbol] = collections.deque(maxlen=config.TICK_HISTORY_SIZE)
            self._epochs[symbol] = collections.deque(maxlen=config.TICK_HISTORY_SIZE)

    def add_tick(self, symbol: str, price: float, epoch: float | None = None) -> None:
        """Record one incoming tick price."""
        self._ensure_symbol(symbol)
        self._prices[symbol].append(price)
        self._digits[symbol].append(self.extract_last_digit(price))
        if epoch is not None:
            self._epochs[symbol].append(float(epoch))

    def add_history(self, symbol: str, prices: list[float]) -> None:
        """Bulk-load historical prices from ticks_history."""
        for price in prices:
            self.add_tick(symbol, float(price))

    @staticmethod
    def extract_last_digit(price: float | str) -> int:
        """Extract the displayed last digit from a tick quote."""
        text = str(price).strip()
        digits = [char for char in text if char.isdigit()]
        return int(digits[-1]) if digits else 0

    def digit_distribution(self, symbol: str, window: int | None = None) -> dict[int, float]:
        """Return fractional frequency of each digit 0-9."""
        digits = list(self._digits.get(symbol, []))
        if window:
            digits = digits[-window:]
        if not digits:
            return {digit: 0.1 for digit in range(10)}
        total = len(digits)
        return {digit: digits.count(digit) / total for digit in range(10)}

    def over3_empirical_rate(self, symbol: str, window: int | None = None) -> float:
        """Fraction of recent digits that are 4-9."""
        distribution = self.digit_distribution(symbol, window or config.ANALYSIS_WINDOW)
        return sum(distribution[digit] for digit in range(4, 10))

    def stability_metrics(self, symbol: str) -> tuple[float, int, float]:
        """Return stability score, spike count, and spike ratio."""
        prices = np.array(list(self._prices.get(symbol, [])), dtype=float)
        if len(prices) < 20:
            return 0.5, 0, 0.0

        deltas = np.abs(np.diff(prices))
        mean_delta = float(np.mean(deltas))
        std_delta = float(np.std(deltas)) + 1e-9
        z_scores = (deltas - mean_delta) / std_delta
        spike_count = int(np.sum(z_scores > config.SPIKE_THRESHOLD))
        spike_ratio = spike_count / max(len(deltas), 1)
        score = max(0.0, 1.0 - (spike_ratio * 5))
        return round(score, 4), spike_count, round(spike_ratio, 4)

    def momentum(self, symbol: str, short: int = 10, long: int = 30) -> float:
        """Compare short and long rolling digit means."""
        digits = list(self._digits.get(symbol, []))
        if len(digits) < long:
            return 0.0
        return round(float(np.mean(digits[-short:]) - np.mean(digits[-long:])), 4)

    def tick_speed(self, symbol: str) -> float:
        """Approximate ticks per second from recent tick epochs."""
        epochs = list(self._epochs.get(symbol, []))
        if len(epochs) < 2:
            return 0.0
        elapsed = max(epochs[-1] - epochs[0], 1e-9)
        return round((len(epochs) - 1) / elapsed, 4)

    def digit_balance_score(self, symbol: str) -> float:
        """Score how close the recent digit distribution is to uniform."""
        distribution = self.digit_distribution(symbol, config.ANALYSIS_WINDOW)
        deviation = sum(abs(distribution[digit] - 0.1) for digit in range(10))
        return round(max(0.0, 1.0 - deviation), 4)

    def compute_stats(self, symbol: str) -> DigitStats:
        """Compute a full DigitStats snapshot for one symbol."""
        digits = list(self._digits.get(symbol, []))
        stats = DigitStats(symbol=symbol, total_ticks=len(digits))
        if not digits:
            return stats

        stats.digit_counts = {digit: digits.count(digit) for digit in range(10)}
        stats.over3_rate = round(self.over3_empirical_rate(symbol), 4)
        stats.stability_score, stats.spike_count, stats.spike_ratio = self.stability_metrics(symbol)
        stats.momentum = self.momentum(symbol)
        stats.tick_speed = self.tick_speed(symbol)
        stats.digit_balance_score = self.digit_balance_score(symbol)
        stats.market_score = self._composite_score(stats)
        return stats

    def _composite_score(self, stats: DigitStats) -> float:
        """Weighted market quality score from probability, stability, and momentum."""
        over3_norm = min(stats.over3_rate / 0.60, 1.0)
        momentum_norm = min(max((stats.momentum + 2.0) / 4.0, 0.0), 1.0)
        tick_speed_norm = min(stats.tick_speed / 2.0, 1.0) if stats.tick_speed else 0.5

        score = (
            0.35 * over3_norm
            + 0.25 * stats.stability_score
            + 0.15 * stats.digit_balance_score
            + 0.15 * momentum_norm
            + 0.10 * tick_speed_norm
        )
        return round(score, 4)
