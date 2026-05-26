"""
strategies/volatility_selector.py — Scans all volatility indices and
returns the best one based on composite market score.
"""

import asyncio
import logging

from analytics.digit_tracker import DigitStats, DigitTracker
from api.deriv_client import DerivClient
import config

logger = logging.getLogger(__name__)


class VolatilitySelector:
    """
    Fetches tick history for all configured symbols, scores each one,
    and returns the symbol with the highest market quality score.
    """

    def __init__(self, client: DerivClient, tracker: DigitTracker):
        self.client = client
        self.tracker = tracker

    async def scan_all(self) -> dict[str, DigitStats]:
        """Fetch history for all symbols and compute their stats in parallel."""
        tasks = [
            self._load_symbol(sym)
            for sym in config.VOLATILITY_INDICES
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        return {
            sym: self.tracker.compute_stats(sym)
            for sym in config.VOLATILITY_INDICES
        }

    async def _load_symbol(self, symbol: str) -> None:
        try:
            prices = await self.client.get_tick_history(
                symbol, count=config.TICK_HISTORY_SIZE
            )
            if prices:
                self.tracker.add_history(symbol, prices)
                logger.debug("Loaded %d ticks for %s", len(prices), symbol)
        except Exception as e:
            logger.warning("Could not load history for %s: %s", symbol, e)

    def best_symbol(self, stats_map: dict[str, DigitStats]) -> str:
        """Return the symbol with the highest market_score."""
        ranked = sorted(
            stats_map.items(),
            key=lambda kv: kv[1].market_score,
            reverse=True,
        )
        best = ranked[0][0] if ranked else config.DEFAULT_SYMBOL
        logger.info(
            "Market ranking: %s",
            [(s, f"{st.market_score:.3f}") for s, st in ranked],
        )
        return best
