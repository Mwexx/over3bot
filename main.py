"""
main.py — Entry point for the Deriv Over 3 Trading Bot.

Usage:
    python main.py

Requires:
    - .env file with DERIV_API_TOKEN set (copy from .env.example)
    - pip install -r requirements.txt
"""

import asyncio
import logging
import os
import signal
import sys

from rich.logging import RichHandler

import config
from analytics.digit_tracker import DigitTracker
from analytics.logs import init_db
from api.deriv_client import create_client_with_retry
from dashboard.terminal import TerminalDashboard
from risk.bankroll import BankrollManager
from strategies.over3_strategy import Over3Strategy


# ─── Logging setup ────────────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        RichHandler(rich_tracebacks=True, show_path=False),
        logging.FileHandler(config.LOG_FILE),
    ],
)
logger = logging.getLogger("main")


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    if not config.API_TOKEN:
        logger.error(
            "DERIV_API_TOKEN not set. Copy .env.example to .env and add your token."
        )
        sys.exit(1)

    # Initialise DB
    init_db()

    # Dashboard
    dashboard = TerminalDashboard()
    await dashboard.start()
    dashboard.add_log("Bot initialising…")

    client = None
    strategy = None

    def _emergency_stop(signum, frame):
        """Handle Ctrl+C or SIGTERM gracefully."""
        logger.warning("Emergency stop signal received.")
        if strategy:
            strategy.running = False
        dashboard.add_log("[bold red]EMERGENCY STOP received[/bold red]")

    signal.signal(signal.SIGINT, _emergency_stop)
    signal.signal(signal.SIGTERM, _emergency_stop)

    reconnect_attempt = 0

    while reconnect_attempt < config.MAX_RECONNECT_ATTEMPTS:
        try:
            # ── Connect & authorise ───────────────────────────────────────
            logger.info("Connecting to Deriv API… (attempt %d)", reconnect_attempt + 1)
            dashboard.add_log(f"Connecting… attempt {reconnect_attempt + 1}")

            client = await create_client_with_retry(config.API_TOKEN)
            balance = await client.get_balance()
            logger.info("Starting balance: %.2f %s", balance, config.CURRENCY)
            dashboard.add_log(f"Connected. Balance: {balance:.2f} {config.CURRENCY}")

            # ── Wire components ───────────────────────────────────────────
            tracker = DigitTracker()
            bankroll = BankrollManager(starting_balance=balance)
            strategy = Over3Strategy(
                client=client,
                tracker=tracker,
                bankroll=bankroll,
                dashboard=dashboard,
            )

            # ── Run strategy loop ─────────────────────────────────────────
            stop_reason = await strategy.run()
            logger.info("Strategy stopped: %s", stop_reason)
            dashboard.add_log(f"Stopped: {stop_reason}")

            # Print final summary
            summary = bankroll.summary()
            logger.info(
                "SESSION SUMMARY | Trades: %d | Win rate: %.1f%% | PnL: %+.2f",
                summary["total_trades"],
                summary["win_rate"],
                summary["session_pnl"],
            )

            # If stop was due to SL/TP/max-trades, don't reconnect
            if stop_reason in ("manual_stop",):
                break
            if "Stop-loss" in stop_reason or "Take-profit" in stop_reason or "Max daily" in stop_reason:
                logger.info("Clean exit. Not reconnecting.")
                break

        except ConnectionError as e:
            reconnect_attempt += 1
            delay = min(config.RECONNECT_DELAY_BASE * (2 ** reconnect_attempt), config.RECONNECT_DELAY_MAX)
            logger.error("Connection error: %s. Reconnecting in %.0fs…", e, delay)
            dashboard.add_log(f"[red]Connection lost. Retry in {delay:.0f}s[/red]")
            await asyncio.sleep(delay)

        except Exception as e:
            logger.critical("Unhandled exception: %s", e, exc_info=True)
            dashboard.add_log(f"[bold red]Critical error: {e}[/bold red]")
            reconnect_attempt += 1
            await asyncio.sleep(10)

        finally:
            if client and client.connected:
                await client.disconnect()

    dashboard.stop()
    logger.info("Bot shut down.")


if __name__ == "__main__":
    asyncio.run(main())
