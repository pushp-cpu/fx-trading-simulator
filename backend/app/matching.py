from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models import CurrencyPair
from app.pricing import quote

def market_fill_price(pair: CurrencyPair, side: str) -> Decimal:
    q = quote(pair)
    if side == "BUY":
        return q["ask"]
    if side == "SELL":
        return q["bid"]
    raise ValueError("side must be BUY or SELL")

def limit_is_marketable(pair: CurrencyPair, side: str, limit_price: Decimal) -> bool:
    q = quote(pair)
    if side == "BUY":
        return q["ask"] <= limit_price
    if side == "SELL":
        return q["bid"] >= limit_price
    raise ValueError("side must be BUY or SELL")
