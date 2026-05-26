"""Entry point for the Deriv Over 3 trading bot."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from rich.logging import RichHandler

import config
from analytics.digit_tracker import DigitTracker
from analytics.logs import init_db
from api.auth import validate_token
from api.deriv_client import create_client_with_retry
from dashboard.terminal import TerminalDashboard
from risk.bankroll import BankrollManager
from strategies.over3_strategy import Over3Strategy


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


async def main() -> None:
    """Start the bot, reconnect on network failures, and stop on risk limits."""
    try:
        validate_token(config.API_TOKEN)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)

    init_db()

    dashboard = TerminalDashboard()
    await dashboard.start()
    dashboard.add_log("Bot initialising.")

    client = None
    strategy: Over3Strategy | None = None

    def emergency_stop(signum, frame) -> None:
        logger.warning("Emergency stop signal received.")
        if strategy:
            strategy.running = False
        dashboard.add_log("[bold red]EMERGENCY STOP received[/bold red]")

    signal.signal(signal.SIGINT, emergency_stop)
    signal.signal(signal.SIGTERM, emergency_stop)

    reconnect_attempt = 0
    while reconnect_attempt < config.MAX_RECONNECT_ATTEMPTS:
        try:
            logger.info("Connecting to Deriv API. Attempt %d", reconnect_attempt + 1)
            dashboard.add_log(f"Connecting. Attempt {reconnect_attempt + 1}")

            client = await create_client_with_retry(config.API_TOKEN)
            balance = await client.get_balance()
            logger.info("Starting balance: %.2f %s", balance, config.CURRENCY)
            dashboard.add_log(f"Connected. Balance: {balance:.2f} {config.CURRENCY}")

            tracker = DigitTracker()
            bankroll = BankrollManager(starting_balance=balance)
            strategy = Over3Strategy(client=client, tracker=tracker, bankroll=bankroll, dashboard=dashboard)

            stop_reason = await strategy.run()
            logger.info("Strategy stopped: %s", stop_reason)
            dashboard.add_log(f"Stopped: {stop_reason}")

            summary = bankroll.summary()
            logger.info(
                "SESSION SUMMARY | Trades: %d | Win rate: %.1f%% | PnL: %+.2f",
                summary["total_trades"],
                summary["win_rate"],
                summary["session_pnl"],
            )

            if stop_reason == "manual_stop":
                break
            if any(marker in stop_reason for marker in ("Stop-loss", "Take-profit", "Max daily")):
                logger.info("Risk limit reached. Not reconnecting.")
                break

            reconnect_attempt = 0

        except ConnectionError as exc:
            reconnect_attempt += 1
            delay = min(config.RECONNECT_DELAY_BASE * (2**reconnect_attempt), config.RECONNECT_DELAY_MAX)
            logger.error("Connection error: %s. Reconnecting in %.0fs.", exc, delay)
            dashboard.add_log(f"[red]Connection lost. Retry in {delay:.0f}s[/red]")
            await asyncio.sleep(delay)

        except Exception as exc:
            reconnect_attempt += 1
            logger.critical("Unhandled exception: %s", exc, exc_info=True)
            dashboard.add_log(f"[bold red]Critical error: {exc}[/bold red]")
            await asyncio.sleep(10)

        finally:
            if client and client.connected:
                await client.disconnect()

    dashboard.stop()
    logger.info("Bot shut down.")


if __name__ == "__main__":
    asyncio.run(main())
