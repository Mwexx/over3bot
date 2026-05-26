"""
config.py — Central configuration for the Deriv Over 3 Bot.
All settings can be overridden via .env variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API ──────────────────────────────────────────────────────────────────────
API_TOKEN: str = os.getenv("DERIV_API_TOKEN", "")
APP_ID: str = os.getenv("DERIV_APP_ID", "1089")
WS_URL: str = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

# ─── Markets ──────────────────────────────────────────────────────────────────
VOLATILITY_INDICES: list[str] = ["R_10", "R_25", "R_50", "R_75", "R_100"]
DEFAULT_SYMBOL: str = "R_100"
BARRIER: str = "3"
CONTRACT_TYPE: str = "DIGITOVER"
DURATION: int = 1
DURATION_UNIT: str = "t"
CURRENCY: str = "USD"

# ─── Staking ──────────────────────────────────────────────────────────────────
BASE_STAKE: float = float(os.getenv("BASE_STAKE", 1.0))
MARTINGALE_MULTIPLIER: float = float(os.getenv("MARTINGALE_MULTIPLIER", 1.5))
MAX_MARTINGALE_STEPS: int = int(os.getenv("MAX_MARTINGALE_STEPS", 4))
# Safer progression: [1, 1, 1.5, 2, 3] instead of aggressive doubling
MARTINGALE_SEQUENCE: list[float] = [
    BASE_STAKE,
    BASE_STAKE,
    BASE_STAKE * 1.5,
    BASE_STAKE * 2.0,
    BASE_STAKE * 3.0,
]

# ─── Risk Management ──────────────────────────────────────────────────────────
STOP_LOSS: float = float(os.getenv("STOP_LOSS", -20.0))          # negative = loss
TAKE_PROFIT: float = float(os.getenv("TAKE_PROFIT", 30.0))
MAX_CONSECUTIVE_LOSSES: int = int(os.getenv("MAX_CONSECUTIVE_LOSSES", 5))
MAX_DAILY_TRADES: int = int(os.getenv("MAX_DAILY_TRADES", 200))
COOLDOWN_SECONDS: float = float(os.getenv("COOLDOWN_SECONDS", 10.0))

# ─── Market Analysis ──────────────────────────────────────────────────────────
TICK_HISTORY_SIZE: int = 200       # ticks kept per symbol
ANALYSIS_WINDOW: int = 100         # last N ticks used for digit analysis
MIN_MARKET_SCORE: float = 0.55     # 0–1; only trade above this threshold
SPIKE_THRESHOLD: float = 3.0       # z-score above which a tick is a spike

# ─── Reconnection ─────────────────────────────────────────────────────────────
MAX_RECONNECT_ATTEMPTS: int = 20
RECONNECT_DELAY_BASE: float = 2.0  # seconds, doubles each attempt (capped at 60)
RECONNECT_DELAY_MAX: float = 60.0

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH: str = "database/trades.db"

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_FILE: str = "logs/bot.log"
LOG_LEVEL: str = "INFO"

# ─── Dashboard ────────────────────────────────────────────────────────────────
DASHBOARD_REFRESH_RATE: float = float(os.getenv("DASHBOARD_REFRESH_RATE", 1.0))
