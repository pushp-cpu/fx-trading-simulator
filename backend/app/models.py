from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.base import Base

def utcnow():
    return datetime.now(timezone.utc)

class CurrencyPair(Base):
    __tablename__ = "currency_pairs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    initial_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    mid: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    drift: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0.02"))
    volatility: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0.12"))
    spread_bps: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("5"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    orders: Mapped[list["Order"]] = relationship(back_populates="pair")
    ticks: Mapped[list["PriceTick"]] = relationship(back_populates="pair")

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair_id: Mapped[int] = mapped_column(ForeignKey("currency_pairs.id"))
    side: Mapped[str] = mapped_column(String(4))
    order_type: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    pair: Mapped["CurrencyPair"] = relationship(back_populates="orders")
    trades: Mapped[list["Trade"]] = relationship(back_populates="order")

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    pair_id: Mapped[int] = mapped_column(ForeignKey("currency_pairs.id"))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    fill_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    order: Mapped["Order"] = relationship(back_populates="trades")

class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("pair_id", name="uq_position_pair"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair_id: Mapped[int] = mapped_column(ForeignKey("currency_pairs.id"))
    net_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"))
    average_entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"))

class PriceTick(Base):
    __tablename__ = "price_ticks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair_id: Mapped[int] = mapped_column(ForeignKey("currency_pairs.id"), index=True)
    mid: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    bid: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    ask: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    pair: Mapped["CurrencyPair"] = relationship(back_populates="ticks")

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equity_inr: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    realized_pnl_inr: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unrealized_pnl_inr: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
