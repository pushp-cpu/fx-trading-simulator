from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING
from datetime import datetime, timezone
from decimal import Decimal
if TYPE_CHECKING:
    from app.models import CurrencyPair

def next_gbm_price(current: Decimal, drift: Decimal, volatility: Decimal,
                   dt_years: float, z: float | None = None) -> Decimal:
    """One geometric-Brownian-motion step; float is used only for stochastic math."""
    if current <= 0 or volatility < 0 or dt_years < 0:
        raise ValueError("Price must be positive; volatility and elapsed time non-negative.")
    normal = random.gauss(0, 1) if z is None else z
    s = float(current)
    mu = float(drift)
    sigma = float(volatility)
    next_value = s * math.exp((mu - 0.5 * sigma * sigma) * dt_years
                              + sigma * math.sqrt(dt_years) * normal)
    return Decimal(str(next_value)).quantize(Decimal("0.00000001"))

def quote(pair: CurrencyPair) -> dict:
    half_spread = pair.mid * pair.spread_bps / Decimal("20000")
    return {
        "symbol": pair.symbol,
        "mid": pair.mid,
        "bid": (pair.mid - half_spread).quantize(Decimal("0.00000001")),
        "ask": (pair.mid + half_spread).quantize(Decimal("0.00000001")),
        "updated_at": pair.updated_at,
    }
