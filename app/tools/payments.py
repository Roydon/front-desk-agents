"""payment_link() - Stripe-style stub URL. The agent never handles card data."""

from __future__ import annotations


def payment_link(reservation_id: str) -> str:
    return f"https://pay.example.test/lakeside/{reservation_id}"
