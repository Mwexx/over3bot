"""Central configuration for the Deriv Over 3 trading bot.

Every setting can be overridden from a local .env file. Keep .env private.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


# API
API_TOKEN: str = os.getenv("DERIV_API_TOKEN", "")
APP_ID: str = os.getenv("DERIV_APP_ID", "1089")
WS_URL: str = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

# Markets
VOLATILITY_INDICES: list[str] = ["R_10", "R_25", "R_50", "R_75", "R_100"]
DEFAULT_SYMBOL: str = os.getenv("DEFAULT_SYMBOL", "R_100")
BARRIER: str = os.getenv("BARRIER", "3")
CONTRACT_TYPE: str = "DIGITOVER"
DURATION: int = _int_env("DURATION", 1)
DURATION_UNIT: str = os.getenv("DURATION_UNIT", "t")
CURRENCY: str = os.getenv("CURRENCY", "USD")

# Staking
BASE_STAKE: float = _float_env("BASE_STAKE", 1.0)
MARTINGALE_MULTIPLIER: float = _float_env("MARTINGALE_MULTIPLIER", 1.5)
MAX_MARTINGALE_STEPS: int = _int_env("MAX_MARTINGALE_STEPS", 4)
USE_SAFE_MARTINGALE_SEQUENCE: bool = os.getenv("USE_SAFE_MARTINGALE_SEQUENCE", "true").lower() == "true"

# Safer progression: 1, 1, 1.5, 2, 3 times base stake.
SAFE_MARTINGALE_FACTORS: list[float] = [1.0, 1.0, 1.5, 2.0, 3.0]
MARTINGALE_SEQUENCE: list[float] = [
    round(BASE_STAKE * factor, 2)
    for factor in SAFE_MARTINGALE_FACTORS[: MAX_MARTINGALE_STEPS + 1]
]

if not USE_SAFE_MARTINGALE_SEQUENCE:
    MARTINGALE_SEQUENCE = [
        round(BASE_STAKE * (MARTINGALE_MULTIPLIER ** step), 2)
        for step in range(MAX_MARTINGALE_STEPS + 1)
    ]

# Risk management
STOP_LOSS: float = _float_env("STOP_LOSS", -20.0)
TAKE_PROFIT: float = _float_env("TAKE_PROFIT", 30.0)
MAX_CONSECUTIVE_LOSSES: int = _int_env("MAX_CONSECUTIVE_LOSSES", 5)
MAX_DAILY_TRADES: int = _int_env("MAX_DAILY_TRADES", 200)
COOLDOWN_SECONDS: float = _float_env("COOLDOWN_SECONDS", 10.0)

# Market analysis
TICK_HISTORY_SIZE: int = _int_env("TICK_HISTORY_SIZE", 200)
ANALYSIS_WINDOW: int = _int_env("ANALYSIS_WINDOW", 100)
MIN_TICKS_TO_TRADE: int = _int_env("MIN_TICKS_TO_TRADE", 50)
MIN_MARKET_SCORE: float = _float_env("MIN_MARKET_SCORE", 0.55)
MIN_STABILITY_SCORE: float = _float_env("MIN_STABILITY_SCORE", 0.40)
MIN_OVER3_RATE: float = _float_env("MIN_OVER3_RATE", 0.52)
SPIKE_THRESHOLD: float = _float_env("SPIKE_THRESHOLD", 3.0)
MAX_SPIKE_RATIO: float = _float_env("MAX_SPIKE_RATIO", 0.10)
MAX_LATENCY_MS: float = _float_env("MAX_LATENCY_MS", 2500.0)
MARKET_RESCAN_SECONDS: float = _float_env("MARKET_RESCAN_SECONDS", 60.0)

# Reconnection
MAX_RECONNECT_ATTEMPTS: int = _int_env("MAX_RECONNECT_ATTEMPTS", 20)
RECONNECT_DELAY_BASE: float = _float_env("RECONNECT_DELAY_BASE", 2.0)
RECONNECT_DELAY_MAX: float = _float_env("RECONNECT_DELAY_MAX", 60.0)
REQUEST_TIMEOUT_SECONDS: float = _float_env("REQUEST_TIMEOUT_SECONDS", 15.0)
CONTRACT_TIMEOUT_SECONDS: float = _float_env("CONTRACT_TIMEOUT_SECONDS", 30.0)

# Storage and logging
DB_PATH: str = os.getenv("DB_PATH", "database/trades.db")
LOG_FILE: str = os.getenv("LOG_FILE", "logs/bot.log")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Dashboard
DASHBOARD_REFRESH_RATE: float = _float_env("DASHBOARD_REFRESH_RATE", 1.0)
