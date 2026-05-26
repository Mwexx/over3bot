"""Adjustable martingale stake progression."""

from __future__ import annotations

import logging

import config

logger = logging.getLogger(__name__)


class MartingaleManager:
    """Returns the next stake using either a safe sequence or multiplier sequence."""

    def __init__(self):
        self.step = 0
        self.sequence = config.MARTINGALE_SEQUENCE

    def current_stake(self) -> float:
        index = min(self.step, len(self.sequence) - 1)
        return round(self.sequence[index], 2)

    def on_win(self) -> None:
        if self.step:
            logger.debug("Martingale reset after win.")
        self.step = 0

    def on_loss(self) -> None:
        self.step = min(self.step + 1, len(self.sequence) - 1)
        logger.debug("Martingale step %d. Next stake: %.2f", self.step, self.current_stake())

    def reset(self) -> None:
        self.step = 0
