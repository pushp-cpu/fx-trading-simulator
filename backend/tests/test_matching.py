from decimal import Decimal as D
from types import SimpleNamespace
from app.matching import limit_is_marketable, market_fill_price
from app.pricing import quote

def pair(mid="1.10000000", spread="10"):
    return SimpleNamespace(symbol="EUR/USD", mid=D(mid), spread_bps=D(spread), updated_at=None)

def test_market_buy_uses_ask():
    p=pair(); assert market_fill_price(p, "BUY") == quote(p)["ask"]

def test_market_sell_uses_bid():
    p=pair(); assert market_fill_price(p, "SELL") == quote(p)["bid"]

def test_limit_buy_fills_if_ask_at_or_below_limit():
    p=pair(); assert limit_is_marketable(p, "BUY", quote(p)["ask"])

def test_limit_buy_waits_when_limit_too_low():
    p=pair(); assert not limit_is_marketable(p, "BUY", D("1.0"))

def test_limit_sell_fills_if_bid_at_or_above_limit():
    p=pair(); assert limit_is_marketable(p, "SELL", quote(p)["bid"])

def test_limit_sell_waits_when_limit_too_high():
    p=pair(); assert not limit_is_marketable(p, "SELL", D("1.2"))
