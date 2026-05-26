"""
api/deriv_client.py — Async WebSocket client for the Deriv API.
Handles auth, subscriptions, contract buying, and auto-reconnect.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine

import websockets
from websockets.exceptions import ConnectionClosed

import config

logger = logging.getLogger(__name__)


class DerivClient:
    """
    Low-level async Deriv WebSocket client.

    Usage:
        client = DerivClient(token)
        await client.connect()
        await client.authorize()
        response = await client.send({"ticks": "R_100"})
        await client.disconnect()
    """

    def __init__(self, token: str):
        self.token = token
        self.ws: websockets.WebSocketClientProtocol | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._req_id: int = 1
        self._tick_callbacks: dict[str, list[Callable]] = {}
        self._listener_task: asyncio.Task | None = None
        self.connected = False
        self.authorized = False
        self.balance: float = 0.0

    # ─── Connection lifecycle ────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open WebSocket connection."""
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
        """Close WebSocket gracefully."""
        self.connected = False
        if self._listener_task:
            self._listener_task.cancel()
        if self.ws:
            await self.ws.close()
        logger.info("WebSocket disconnected.")

    async def authorize(self) -> dict:
        """Send authorization and cache balance."""
        resp = await self.send({"authorize": self.token})
        if "error" in resp:
            raise PermissionError(f"Auth failed: {resp['error']['message']}")
        self.authorized = True
        self.balance = resp.get("authorize", {}).get("balance", 0.0)
        logger.info("Authorized. Balance: %.2f %s", self.balance, config.CURRENCY)
        return resp

    # ─── Send / receive ──────────────────────────────────────────────────────

    async def send(self, payload: dict) -> dict:
        """
        Send a request and await its response by req_id.
        Thread-safe via asyncio Future.
        """
        req_id = self._req_id
        self._req_id += 1
        payload["req_id"] = req_id

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        await self.ws.send(json.dumps(payload))
        try:
            return await asyncio.wait_for(future, timeout=15.0)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"Request {req_id} timed out: {payload}")

    async def _listen(self) -> None:
        """Background task: route incoming messages to futures or callbacks."""
        try:
            async for raw in self.ws:
                msg: dict = json.loads(raw)
                req_id = msg.get("req_id")

                # Route to waiting send() caller
                if req_id and req_id in self._pending:
                    future = self._pending.pop(req_id)
                    if not future.done():
                        future.set_result(msg)

                # Route tick stream to registered callbacks
                if msg.get("msg_type") == "tick":
                    symbol = msg["tick"]["symbol"]
                    for cb in self._tick_callbacks.get(symbol, []):
                        asyncio.create_task(cb(msg["tick"]))

                # Update balance from any proposal_open_contract
                if msg.get("msg_type") == "balance":
                    self.balance = msg["balance"]["balance"]

        except ConnectionClosed as e:
            logger.warning("WebSocket connection closed: %s", e)
            self.connected = False
        except Exception as e:
            logger.error("Listener error: %s", e, exc_info=True)
            self.connected = False

    # ─── Subscriptions ───────────────────────────────────────────────────────

    def on_tick(self, symbol: str, callback: Callable) -> None:
        """Register a callback for live tick data for a symbol."""
        self._tick_callbacks.setdefault(symbol, []).append(callback)

    async def subscribe_ticks(self, symbol: str) -> None:
        """Subscribe to live ticks for a volatility index."""
        await self.send({"ticks": symbol, "subscribe": 1})
        logger.debug("Subscribed to ticks: %s", symbol)

    async def unsubscribe_ticks(self, symbol: str) -> None:
        """Unsubscribe from tick stream."""
        await self.send({"forget_all": "ticks"})
        logger.debug("Unsubscribed from ticks: %s", symbol)

    # ─── Tick history ────────────────────────────────────────────────────────

    async def get_tick_history(self, symbol: str, count: int = 200) -> list[float]:
        """Fetch recent tick history for analysis."""
        resp = await self.send({
            "ticks_history": symbol,
            "count": count,
            "end": "latest",
            "style": "ticks",
        })
        if "error" in resp:
            logger.error("Tick history error for %s: %s", symbol, resp["error"])
            return []
        return resp.get("history", {}).get("prices", [])

    # ─── Trading ─────────────────────────────────────────────────────────────

    async def get_balance(self) -> float:
        """Fetch current account balance."""
        resp = await self.send({"balance": 1})
        if "error" not in resp:
            self.balance = resp["balance"]["balance"]
        return self.balance

    async def buy_over3(self, symbol: str, stake: float) -> dict:
        """
        Buy one DIGITOVER 3 contract.
        Returns the full buy response.
        """
        # Step 1: Get proposal price
        proposal = await self.send({
            "proposal": 1,
            "amount": round(stake, 2),
            "basis": "stake",
            "contract_type": config.CONTRACT_TYPE,
            "currency": config.CURRENCY,
            "duration": config.DURATION,
            "duration_unit": config.DURATION_UNIT,
            "symbol": symbol,
            "barrier": config.BARRIER,
        })

        if "error" in proposal:
            raise ValueError(f"Proposal error: {proposal['error']['message']}")

        proposal_id = proposal["proposal"]["id"]
        buy_price = proposal["proposal"]["ask_price"]

        # Step 2: Buy
        buy_resp = await self.send({
            "buy": proposal_id,
            "price": buy_price,
        })

        if "error" in buy_resp:
            raise ValueError(f"Buy error: {buy_resp['error']['message']}")

        return buy_resp

    async def wait_for_contract_result(self, contract_id: int) -> dict:
        """Poll until the contract settles and return final status."""
        for _ in range(30):
            resp = await self.send({
                "proposal_open_contract": 1,
                "contract_id": contract_id,
            })
            poc = resp.get("proposal_open_contract", {})
            if poc.get("is_settled") or poc.get("is_expired"):
                return poc
            await asyncio.sleep(1.0)
        raise TimeoutError(f"Contract {contract_id} did not settle in time.")


# ─── Reconnecting wrapper ────────────────────────────────────────────────────

async def create_client_with_retry(token: str) -> DerivClient:
    """
    Create and authorize a DerivClient, retrying on failure.
    Uses exponential backoff capped at RECONNECT_DELAY_MAX.
    """
    attempt = 0
    delay = config.RECONNECT_DELAY_BASE

    while attempt < config.MAX_RECONNECT_ATTEMPTS:
        try:
            client = DerivClient(token)
            await client.connect()
            await client.authorize()
            return client
        except Exception as e:
            attempt += 1
            logger.warning(
                "Connection attempt %d/%d failed: %s. Retrying in %.1fs…",
                attempt, config.MAX_RECONNECT_ATTEMPTS, e, delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, config.RECONNECT_DELAY_MAX)

    raise ConnectionError("Exhausted all reconnect attempts.")
