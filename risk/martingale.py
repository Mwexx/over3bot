"""
risk/martingale.py — Manages stake progression using a safer
martingale sequence (not pure doubling).
"""

import logging
import config

logger = logging.getLogger(__name__)


class MartingaleManager:
    """
    Tracks consecutive losses and returns the appropriate stake.

    Default safer sequence: [1, 1, 1.5, 2, 3] × BASE_STAKE
    instead of aggressive exponential doubling.
    """

    def __init__(self):
        self.step: int = 0
        self.sequence: list[float] = config.MARTINGALE_SEQUENCE

    def current_stake(self) -> float:
        idx = min(self.step, len(self.sequence) - 1)
        return round(self.sequence[idx], 2)

    def on_win(self) -> None:
        """Reset to base stake after a win."""
        if self.step != 0:
            logger.debug("Martingale reset after win.")
        self.step = 0

    def on_loss(self) -> None:
        """Advance to next martingale step after a loss."""
        self.step = min(self.step + 1, len(self.sequence) - 1)
        logger.debug(
            "Martingale step → %d (next stake: %.2f)",
            self.step, self.current_stake(),
        )

    def reset(self) -> None:
        self.step = 0
