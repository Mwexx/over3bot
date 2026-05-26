"""SQLite trade logger and summary queries."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    return sqlite3.connect(config.DB_PATH)


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _ensure_column(conn: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    if name not in _existing_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_db() -> None:
    """Create or migrate the SQLite schema."""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                stake REAL NOT NULL,
                last_digit INTEGER,
                result TEXT NOT NULL,
                pnl REAL NOT NULL,
                balance REAL,
                market_score REAL,
                martingale_step INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                session_pnl REAL DEFAULT 0.0,
                stop_reason TEXT
            )
            """
        )
        _ensure_column(conn, "trades", "latency_ms", "REAL")
        _ensure_column(conn, "trades", "execution_ms", "REAL")
        _ensure_column(conn, "trades", "over3_rate", "REAL")
        _ensure_column(conn, "trades", "stability_score", "REAL")
        _ensure_column(conn, "trades", "spike_ratio", "REAL")
        _ensure_column(conn, "trades", "momentum", "REAL")
    logger.info("Database initialised at %s", config.DB_PATH)


def log_trade(
    *,
    symbol: str,
    stake: float,
    last_digit: int | None,
    result: str,
    pnl: float,
    balance: float,
    market_score: float,
    martingale_step: int,
    latency_ms: float | None = None,
    execution_ms: float | None = None,
    over3_rate: float | None = None,
    stability_score: float | None = None,
    spike_ratio: float | None = None,
    momentum: float | None = None,
) -> None:
    """Insert one trade record."""
    try:
        with _conn() as conn:
            conn.execute(
                """
                INSERT INTO trades (
                    timestamp, symbol, stake, last_digit, result, pnl, balance,
                    market_score, martingale_step, latency_ms, execution_ms,
                    over3_rate, stability_score, spike_ratio, momentum
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now(),
                    symbol,
                    stake,
                    last_digit,
                    result,
                    pnl,
                    balance,
                    market_score,
                    martingale_step,
                    latency_ms,
                    execution_ms,
                    over3_rate,
                    stability_score,
                    spike_ratio,
                    momentum,
                ),
            )
    except Exception as exc:
        logger.error("Failed to log trade: %s", exc)


def get_session_summary() -> dict:
    """Return aggregated stats for the current UTC calendar day."""
    today = datetime.now(timezone.utc).date().isoformat()
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(pnl) AS net_pnl,
                SUM(result='win') AS wins,
                SUM(result='loss') AS losses,
                AVG(market_score) AS avg_score,
                AVG(CASE WHEN result='win' THEN pnl END) AS avg_win,
                AVG(CASE WHEN result='loss' THEN pnl END) AS avg_loss,
                AVG(latency_ms) AS avg_latency,
                AVG(execution_ms) AS avg_execution
            FROM trades
            WHERE timestamp LIKE ?
            """,
            (f"{today}%",),
        ).fetchone()

    total = row[0] if row else 0
    wins = row[2] or 0 if row else 0
    return {
        "total_trades": total,
        "net_pnl": round(row[1] or 0.0, 2) if row else 0.0,
        "wins": wins,
        "losses": row[3] or 0 if row else 0,
        "avg_market_score": round(row[4] or 0.0, 4) if row else 0.0,
        "avg_profit": round(row[5] or 0.0, 2) if row else 0.0,
        "avg_loss": round(row[6] or 0.0, 2) if row else 0.0,
        "avg_latency_ms": round(row[7] or 0.0, 2) if row else 0.0,
        "avg_execution_ms": round(row[8] or 0.0, 2) if row else 0.0,
        "win_rate": round((wins / total * 100) if total else 0.0, 1),
    }
