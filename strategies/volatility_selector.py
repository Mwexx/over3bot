"""Dynamic volatility index scanner."""

from __future__ import annotations

import asyncio
import logging

from analytics.digit_tracker import DigitStats, DigitTracker
from api.deriv_client import DerivClient
import config

logger = logging.getLogger(__name__)


class VolatilitySelector:
    """Fetches tick history, scores configured volatility indices, and ranks them."""

    def __init__(self, client: DerivClient, tracker: DigitTracker):
        self.client = client
        self.tracker = tracker

    async def scan_all(self) -> dict[str, DigitStats]:
        tasks = [self._load_symbol(symbol) for symbol in config.VOLATILITY_INDICES]
        await asyncio.gather(*tasks, return_exceptions=True)
        return {symbol: self.tracker.compute_stats(symbol) for symbol in config.VOLATILITY_INDICES}

    async def _load_symbol(self, symbol: str) -> None:
        try:
            prices = await self.client.get_tick_history(symbol, count=config.TICK_HISTORY_SIZE)
            if prices:
                self.tracker.add_history(symbol, prices)
                logger.debug("Loaded %d ticks for %s", len(prices), symbol)
        except Exception as exc:
            logger.warning("Could not load history for %s: %s", symbol, exc)

    def best_symbol(self, stats_map: dict[str, DigitStats]) -> str:
        ranked = sorted(stats_map.items(), key=lambda item: item[1].market_score, reverse=True)
        best = ranked[0][0] if ranked else config.DEFAULT_SYMBOL
        logger.info("Market ranking: %s", [(symbol, f"{stats.market_score:.3f}") for symbol, stats in ranked])
        return best
