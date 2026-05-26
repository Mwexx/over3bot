"""Async WebSocket client for the Deriv API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

import config

TickCallback = Callable[[dict[str, Any]], Awaitable[None]]

logger = logging.getLogger(__name__)


class DerivClient:
    """Low-level async Deriv WebSocket client."""

    def __init__(self, token: str):
        self.token = token
        self.ws: websockets.WebSocketClientProtocol | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._req_id = 1
        self._tick_callbacks: dict[str, TickCallback] = {}
        self._subscriptions: set[str] = set()
        self._listener_task: asyncio.Task | None = None
        self.connected = False
        self.authorized = False
        self.balance = 0.0
        self.last_latency_ms = 0.0

    async def connect(self) -> None:
        """Open the WebSocket connection."""
        self.ws = await websockets.connect(
            config.WS_URL,
            ping_interval=30,
            ping_timeout=10,
            close_timeout=5,
        )
        self.connected = True
        self._listener_task = asyncio.create_task(self._listen())
        logger.info("WebSocket connected: %s", config.WS_URL)

    async def disconnect(self) -> None:
        """Close the WebSocket connection cleanly."""
        self.connected = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
        self._subscriptions.clear()
        logger.info("WebSocket disconnected.")

    async def authorize(self) -> dict[str, Any]:
        """Authorize the account and cache the balance."""
        response = await self.send({"authorize": self.token})
        if "error" in response:
            raise PermissionError(f"Auth failed: {response['error']['message']}")
        auth = response.get("authorize", {})
        self.authorized = True
        self.balance = float(auth.get("balance", 0.0))
        logger.info("Authorized. Balance: %.2f %s", self.balance, config.CURRENCY)
        return response

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one request and wait for the response with matching req_id."""
        if not self.ws or not self.connected:
            raise ConnectionError("WebSocket is not connected.")

        req_id = self._req_id
        self._req_id += 1
        request = dict(payload)
        request["req_id"] = req_id

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future

        started = time.perf_counter()
        await self.ws.send(json.dumps(request))
        try:
            response = await asyncio.wait_for(future, timeout=config.REQUEST_TIMEOUT_SECONDS)
            self.last_latency_ms = (time.perf_counter() - started) * 1000
            return response
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"Request {req_id} timed out: {payload}")

    async def _listen(self) -> None:
        """Route incoming messages to waiting futures or tick callbacks."""
        try:
            async for raw in self.ws:
                message: dict[str, Any] = json.loads(raw)
                req_id = message.get("req_id")

                if req_id and req_id in self._pending:
                    future = self._pending.pop(req_id)
                    if not future.done():
                        future.set_result(message)

                if message.get("msg_type") == "tick":
                    tick = message["tick"]
                    callback = self._tick_callbacks.get(tick["symbol"])
                    if callback:
                        asyncio.create_task(callback(tick))

                if message.get("msg_type") == "balance":
                    self.balance = float(message["balance"]["balance"])

        except ConnectionClosed as exc:
            logger.warning("WebSocket connection closed: %s", exc)
            self.connected = False
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Listener error: %s", exc, exc_info=True)
            self.connected = False

    def set_tick_callback(self, symbol: str, callback: TickCallback) -> None:
        """Set one callback per symbol to avoid duplicate callbacks after rescans."""
        self._tick_callbacks[symbol] = callback

    async def subscribe_ticks(self, symbol: str) -> None:
        """Subscribe to live ticks for a volatility index."""
        if symbol in self._subscriptions:
            return
        response = await self.send({"ticks": symbol, "subscribe": 1})
        if "error" in response:
            raise ValueError(f"Tick subscription failed: {response['error']['message']}")
        self._subscriptions.add(symbol)
        logger.debug("Subscribed to ticks: %s", symbol)

    async def unsubscribe_all_ticks(self) -> None:
        """Unsubscribe from all active tick streams."""
        if not self._subscriptions:
            return
        await self.send({"forget_all": "ticks"})
        self._subscriptions.clear()
        logger.debug("Unsubscribed from all ticks.")

    async def get_tick_history(self, symbol: str, count: int = 200) -> list[float]:
        """Fetch recent tick history for analysis."""
        response = await self.send(
            {
                "ticks_history": symbol,
                "count": count,
                "end": "latest",
                "style": "ticks",
            }
        )
        if "error" in response:
            logger.error("Tick history error for %s: %s", symbol, response["error"])
            return []
        return [float(price) for price in response.get("history", {}).get("prices", [])]

    async def get_balance(self) -> float:
        """Fetch current account balance."""
        response = await self.send({"balance": 1})
        if "error" not in response:
            self.balance = float(response["balance"]["balance"])
        return self.balance

    async def buy_over3(self, symbol: str, stake: float) -> dict[str, Any]:
        """Buy one DIGITOVER 3 contract and include timing metadata."""
        started = time.perf_counter()
        proposal = await self.send(
            {
                "proposal": 1,
                "amount": round(stake, 2),
                "basis": "stake",
                "contract_type": config.CONTRACT_TYPE,
                "currency": config.CURRENCY,
                "duration": config.DURATION,
                "duration_unit": config.DURATION_UNIT,
                "symbol": symbol,
                "barrier": config.BARRIER,
            }
        )
        proposal_latency = self.last_latency_ms

        if "error" in proposal:
            raise ValueError(f"Proposal error: {proposal['error']['message']}")

        proposal_data = proposal["proposal"]
        buy_response = await self.send(
            {
                "buy": proposal_data["id"],
                "price": proposal_data["ask_price"],
            }
        )
        buy_latency = self.last_latency_ms

        if "error" in buy_response:
            raise ValueError(f"Buy error: {buy_response['error']['message']}")

        buy_response["_proposal_latency_ms"] = round(proposal_latency, 2)
        buy_response["_buy_latency_ms"] = round(buy_latency, 2)
        buy_response["_execution_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return buy_response

    async def wait_for_contract_result(self, contract_id: int) -> dict[str, Any]:
        """Poll until the contract settles, then return the final contract data."""
        deadline = time.monotonic() + config.CONTRACT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            response = await self.send(
                {
                    "proposal_open_contract": 1,
                    "contract_id": contract_id,
                }
            )
            if "error" in response:
                raise ValueError(f"Contract check error: {response['error']['message']}")
            contract = response.get("proposal_open_contract", {})
            if contract.get("contract_id") != contract_id:
                raise ValueError("Contract verification failed: mismatched contract id.")
            if contract.get("is_settled") or contract.get("is_expired"):
                return contract
            await asyncio.sleep(1.0)
        raise TimeoutError(f"Contract {contract_id} did not settle in time.")


async def create_client_with_retry(token: str) -> DerivClient:
    """Create and authorize a DerivClient with exponential backoff."""
    attempt = 0
    delay = config.RECONNECT_DELAY_BASE

    while attempt < config.MAX_RECONNECT_ATTEMPTS:
        client = DerivClient(token)
        try:
            await client.connect()
            await client.authorize()
            return client
        except Exception as exc:
            await client.disconnect()
            attempt += 1
            logger.warning(
                "Connection attempt %d/%d failed: %s. Retrying in %.1fs.",
                attempt,
                config.MAX_RECONNECT_ATTEMPTS,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, config.RECONNECT_DELAY_MAX)

    raise ConnectionError("Exhausted all reconnect attempts.")
