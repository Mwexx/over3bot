"""
analytics/logs.py — SQLite trade logger and performance analytics.
"""

import logging
import os
import sqlite3
from datetime import datetime

import config

logger = logging.getLogger(__name__)


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    return sqlite3.connect(config.DB_PATH)


def init_db() -> None:
    """Create tables if they don't exist."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                symbol      TEXT    NOT NULL,
                stake       REAL    NOT NULL,
                last_digit  INTEGER,
                result      TEXT    NOT NULL,   -- 'win' | 'loss'
                pnl         REAL    NOT NULL,
                balance     REAL,
                market_score REAL,
                martingale_step INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT    NOT NULL,
                ended_at    TEXT,
                total_trades INTEGER DEFAULT 0,
                wins        INTEGER DEFAULT 0,
                losses      INTEGER DEFAULT 0,
                session_pnl REAL    DEFAULT 0.0,
                stop_reason TEXT
            )
        """)
    logger.info("Database initialised at %s", config.DB_PATH)


def log_trade(
    symbol: str,
    stake: float,
    last_digit: int | None,
    result: str,
    pnl: float,
    balance: float,
    market_score: float,
    martingale_step: int,
) -> None:
    """Insert one trade record."""
    try:
        with _conn() as conn:
            conn.execute(
                """
                INSERT INTO trades
                  (timestamp, symbol, stake, last_digit, result, pnl,
                   balance, market_score, martingale_step)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    symbol, stake, last_digit, result,
                    pnl, balance, market_score, martingale_step,
                ),
            )
    except Exception as e:
        logger.error("Failed to log trade: %s", e)


def get_session_summary() -> dict:
    """Return aggregated stats for the current calendar day."""
    today = datetime.utcnow().date().isoformat()
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)              AS total,
                SUM(pnl)              AS net_pnl,
                SUM(result='win')     AS wins,
                SUM(result='loss')    AS losses,
                AVG(market_score)     AS avg_score
            FROM trades
            WHERE timestamp LIKE ?
            """,
            (f"{today}%",),
        ).fetchone()
    if not row:
        return {}
    return {
        "total_trades": row[0],
        "net_pnl": round(row[1] or 0, 2),
        "wins": row[2],
        "losses": row[3],
        "avg_market_score": round(row[4] or 0, 4),
        "win_rate": round((row[2] / row[0] * 100) if row[0] else 0, 1),
    }
