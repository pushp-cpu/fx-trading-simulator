from decimal import Decimal as D
import pytest
from app.accounting import apply_fill, max_drawdown, unrealized_pnl
from app.models import Position
from app.pricing import next_gbm_price

def pos():
    return Position(net_quantity=D("0"), average_entry_price=D("0"), realized_pnl=D("0"))

def fill(p, side, qty, price):
    return apply_fill(p, side, D(qty), D(price))

def test_first_buy_sets_position_and_average():
    p = fill(pos(), "BUY", "10", "1.10")
    assert p.net_quantity == D("10")
    assert p.average_entry_price == D("1.10")

def test_multiple_buys_use_weighted_average():
    p = pos(); fill(p, "BUY", "10", "1.10"); fill(p, "BUY", "10", "1.20")
    assert p.net_quantity == D("20")
    assert p.average_entry_price == D("1.15")

def test_three_buys_weight_average():
    p = pos(); fill(p, "BUY", "2", "1.00"); fill(p, "BUY", "4", "1.10"); fill(p, "BUY", "6", "1.20")
    assert p.average_entry_price == D("1.133333333333333333333333333")

def test_long_unrealized_profit():
    p = fill(pos(), "BUY", "10", "1.10")
    assert unrealized_pnl(p, D("1.20")) == D("1.00")

def test_long_unrealized_loss():
    p = fill(pos(), "BUY", "10", "1.10")
    assert unrealized_pnl(p, D("1.00")) == D("-1.00")

def test_sell_partial_close_realizes_profit():
    p = fill(pos(), "BUY", "10", "1.10"); fill(p, "SELL", "4", "1.20")
    assert p.net_quantity == D("6")
    assert p.realized_pnl == D("0.40")
    assert p.average_entry_price == D("1.10")

def test_sell_partial_close_realizes_loss():
    p = fill(pos(), "BUY", "10", "1.10"); fill(p, "SELL", "4", "1.00")
    assert p.net_quantity == D("6")
    assert p.realized_pnl == D("-0.40")

def test_full_close_resets_average():
    p = fill(pos(), "BUY", "10", "1.10"); fill(p, "SELL", "10", "1.20")
    assert p.net_quantity == D("0")
    assert p.average_entry_price == D("0")
    assert p.realized_pnl == D("1.00")

def test_flip_long_to_short():
    p = fill(pos(), "BUY", "10", "1.10"); fill(p, "SELL", "15", "1.20")
    assert p.net_quantity == D("-5")
    assert p.average_entry_price == D("1.20")
    assert p.realized_pnl == D("1.00")

def test_flip_short_to_long():
    p = fill(pos(), "SELL", "10", "1.20"); fill(p, "BUY", "15", "1.10")
    assert p.net_quantity == D("5")
    assert p.average_entry_price == D("1.10")
    assert p.realized_pnl == D("1.00")

def test_short_unrealized_profit_when_price_falls():
    p = fill(pos(), "SELL", "10", "1.20")
    assert unrealized_pnl(p, D("1.10")) == D("1.00")

def test_short_unrealized_loss_when_price_rises():
    p = fill(pos(), "SELL", "10", "1.20")
    assert unrealized_pnl(p, D("1.30")) == D("-1.00")

def test_invalid_side_rejected():
    with pytest.raises(ValueError): fill(pos(), "HOLD", "1", "1.1")

def test_zero_quantity_rejected():
    with pytest.raises(ValueError): fill(pos(), "BUY", "0", "1.1")

def test_negative_price_rejected():
    with pytest.raises(ValueError): fill(pos(), "BUY", "1", "-1")

def test_max_drawdown_percentage_fraction():
    assert max_drawdown([D("100"), D("120"), D("90"), D("110")]) == D("0.25")

def test_no_drawdown_on_monotonic_equity():
    assert max_drawdown([D("100"), D("110"), D("120")]) == D("0")

def test_gbm_deterministic_when_volatility_zero():
    actual = next_gbm_price(D("100"), D("0"), D("0"), 1, z=0)
    assert actual == D("100.00000000")

def test_gbm_rejects_nonpositive_price():
    with pytest.raises(ValueError): next_gbm_price(D("0"), D("0"), D("0"), 1, z=0)
