"""In-memory performance analytics for the active bot session."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class PerformanceTracker:
    """Tracks session performance without slowing down the trade loop."""

    recent_results: deque[str] = field(default_factory=lambda: deque(maxlen=100))
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    execution_ms: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    pnl_by_symbol: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    trades_by_symbol: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_trade(self, symbol: str, result: str, pnl: float, latency_ms: float, execution_ms: float) -> None:
        self.recent_results.append(result)
        if latency_ms:
            self.latencies_ms.append(latency_ms)
        if execution_ms:
            self.execution_ms.append(execution_ms)
        self.pnl_by_symbol[symbol] += pnl
        self.trades_by_symbol[symbol] += 1

    @staticmethod
    def _avg(values: deque[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    def summary(self) -> dict:
        wins = sum(1 for result in self.recent_results if result == "win")
        total = len(self.recent_results)
        ranked = sorted(self.pnl_by_symbol.items(), key=lambda item: item[1], reverse=True)
        return {
            "recent_win_rate": round((wins / total * 100) if total else 0.0, 1),
            "avg_latency_ms": self._avg(self.latencies_ms),
            "avg_execution_ms": self._avg(self.execution_ms),
            "best_market": ranked[0][0] if ranked else "",
            "worst_market": ranked[-1][0] if ranked else "",
        }
