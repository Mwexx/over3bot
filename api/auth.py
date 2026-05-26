"""Authentication helpers for Deriv API tokens."""

from __future__ import annotations


def validate_token(token: str) -> None:
    """Fail fast on missing placeholder tokens."""
    if not token or token.strip() in {"", "your_api_token_here"}:
        raise ValueError("DERIV_API_TOKEN is missing. Copy .env.example to .env and add a real token.")
