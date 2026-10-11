from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field

class OrderCreate(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    limit_price: Decimal | None = Field(default=None, gt=0)

class OrderOut(BaseModel):
    id: int
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    limit_price: Decimal | None
    status: str
    fill_price: Decimal | None = None
    created_at: datetime

class PriceOut(BaseModel):
    symbol: str
    mid: Decimal
    bid: Decimal
    ask: Decimal
    updated_at: datetime

class PositionOut(BaseModel):
    symbol: str
    net_quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
