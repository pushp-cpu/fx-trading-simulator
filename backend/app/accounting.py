from decimal import Decimal
from app.models import Position

ZERO = Decimal("0")

def apply_fill(position: Position, side: str, quantity: Decimal, price: Decimal) -> Position:
    """Average-cost accounting. Positive quantity is long; negative is short.
    Realized P&L is reported in the pair's quote currency.
    """
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if quantity <= 0 or price <= 0:
        raise ValueError("quantity and price must be positive")
    signed = quantity if side == "BUY" else -quantity
    old_qty = Decimal(position.net_quantity or ZERO)
    old_avg = Decimal(position.average_entry_price or ZERO)
    realized = Decimal(position.realized_pnl or ZERO)

    if old_qty == 0 or (old_qty > 0 and signed > 0) or (old_qty < 0 and signed < 0):
        new_qty = old_qty + signed
        new_avg = ((abs(old_qty) * old_avg + abs(signed) * price) / abs(new_qty))
    else:
        closed = min(abs(old_qty), abs(signed))
        realized += closed * (price - old_avg) * (Decimal("1") if old_qty > 0 else Decimal("-1"))
        new_qty = old_qty + signed
        if new_qty == 0:
            new_avg = ZERO
        elif (new_qty > 0) != (old_qty > 0):
            # A flip opens the excess on the opposite side at the new fill price.
            new_avg = price
        else:
            new_avg = old_avg

    position.net_quantity = new_qty
    position.average_entry_price = new_avg
    position.realized_pnl = realized
    return position

def unrealized_pnl(position: Position, close_price: Decimal) -> Decimal:
    qty = Decimal(position.net_quantity or ZERO)
    avg = Decimal(position.average_entry_price or ZERO)
    return qty * (close_price - avg)

def max_drawdown(equity_curve: list[Decimal]) -> Decimal:
    peak = None
    worst = Decimal("0")
    for value in equity_curve:
        peak = value if peak is None else max(peak, value)
        if peak and peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst
