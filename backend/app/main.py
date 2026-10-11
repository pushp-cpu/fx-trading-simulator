
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting import apply_fill, max_drawdown, unrealized_pnl
from app.config import TICK_INTERVAL_SECONDS
from app.database import Base, SessionLocal, engine, get_db
from app.matching import limit_is_marketable, market_fill_price
from app.models import (
    CurrencyPair,
    Order,
    Position,
    PortfolioSnapshot,
    PriceTick,
    Trade,
)
from app.pricing import next_gbm_price, quote
from app.schemas import OrderCreate


DEFAULT_PAIRS = [
    ("USD/INR", "83.00000000", "0.03", "0.10", "5"),
    ("EUR/USD", "1.08000000", "0.02", "0.12", "4"),
    ("GBP/USD", "1.27000000", "0.02", "0.14", "5"),
    ("USD/JPY", "150.00000000", "0.01", "0.11", "4"),
    ("EUR/INR", "89.60000000", "0.03", "0.13", "6"),
]


def initialize_database():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for symbol, price, drift, vol, spread in DEFAULT_PAIRS:
            pair = db.scalar(
                select(CurrencyPair).where(CurrencyPair.symbol == symbol)
            )

            if pair is None:
                pair = CurrencyPair(
                    symbol=symbol,
                    initial_price=Decimal(price),
                    mid=Decimal(price),
                    drift=Decimal(drift),
                    volatility=Decimal(vol),
                    spread_bps=Decimal(spread),
                )
                db.add(pair)
                db.flush()

                db.add(
                    PriceTick(
                        pair_id=pair.id,
                        mid=pair.mid,
                        bid=quote(pair)["bid"],
                        ask=quote(pair)["ask"],
                    )
                )

        db.commit()


def match_pending(db: Session, pair: CurrencyPair):
    pending = db.scalars(
        select(Order)
        .where(
            Order.pair_id == pair.id,
            Order.status == "PENDING",
        )
        .order_by(Order.created_at, Order.id)
    ).all()

    for order in pending:
        if order.order_type != "LIMIT" or order.limit_price is None:
            continue

        if limit_is_marketable(pair, order.side, order.limit_price):
            fill_order(
                db,
                order,
                pair,
                market_fill_price(pair, order.side),
            )


def fill_order(
    db: Session,
    order: Order,
    pair: CurrencyPair,
    price: Decimal,
):
    trade = Trade(
        order_id=order.id,
        pair_id=pair.id,
        side=order.side,
        quantity=order.quantity,
        fill_price=price,
        fee=Decimal("0"),
    )
    db.add(trade)

    position = db.scalar(
        select(Position).where(Position.pair_id == pair.id)
    )

    if position is None:
        position = Position(
            pair_id=pair.id,
            net_quantity=Decimal("0"),
            average_entry_price=Decimal("0"),
            realized_pnl=Decimal("0"),
        )
        db.add(position)
        db.flush()

    apply_fill(position, order.side, Decimal(order.quantity), price)
    order.status = "FILLED"


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    task = asyncio.create_task(price_loop())

    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="FX Trading Simulator API",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow local development and the deployed Vercel frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://fx-trading-simulator-oozl2xc6m-pushp-cpu.vercel.app",
        "https://fx-trading-simulator-avqtxcug-pushp-cpu.vercel.app",
        "https://fx-trading-simulator-q2ks4jbm8-pushp-cpu.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def price_loop():
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)

        with SessionLocal() as db:
            pairs = db.scalars(select(CurrencyPair)).all()

            for pair in pairs:
                pair.mid = next_gbm_price(
                    pair.mid,
                    pair.drift,
                    pair.volatility,
                    1 / (365.25 * 24 * 60 * 60),
                )
                pair.updated_at = datetime.now(timezone.utc)

                q = quote(pair)
                db.add(
                    PriceTick(
                        pair_id=pair.id,
                        mid=q["mid"],
                        bid=q["bid"],
                        ask=q["ask"],
                    )
                )

                match_pending(db, pair)

            db.commit()
            record_snapshot(db)
            db.commit()


def record_snapshot(db: Session):
    positions = db.scalars(select(Position)).all()
    total_unrealized = Decimal("0")
    total_realized = Decimal("0")

    for pos in positions:
        pair = db.get(CurrencyPair, pos.pair_id)

        if pair:
            q = quote(pair)
            close_price = q["bid"] if pos.net_quantity > 0 else q["ask"]

            total_unrealized += (
                unrealized_pnl(pos, close_price)
                * fx_to_inr(pair.symbol, pair.mid)
            )
            total_realized += (
                Decimal(pos.realized_pnl)
                * fx_to_inr(pair.symbol, pair.mid)
            )

    db.add(
        PortfolioSnapshot(
            equity_inr=Decimal("1000000")
            + total_realized
            + total_unrealized,
            realized_pnl_inr=total_realized,
            unrealized_pnl_inr=total_unrealized,
        )
    )

    # Keep the demo database from growing without limit.
    old = db.scalars(
        select(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.id.desc())
        .offset(86400)
    ).all()

    for row in old:
        db.delete(row)


def fx_to_inr(symbol: str, mid: Decimal) -> Decimal:
    if symbol.endswith("/INR"):
        return Decimal("1")

    if symbol == "EUR/USD":
        return Decimal("83")  # Illustrative USD/INR conversion rate.

    if symbol == "GBP/USD":
        return Decimal("83")

    if symbol == "USD/JPY":
        return Decimal("83") / mid

    return Decimal("1")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/prices")
def prices(db: Session = Depends(get_db)):
    return [
        quote(pair)
        for pair in db.scalars(
            select(CurrencyPair).order_by(CurrencyPair.symbol)
        ).all()
    ]


@app.get("/api/prices/history")
def price_history(
    symbol: str,
    limit: int = Query(default=120, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    pair = db.scalar(
        select(CurrencyPair).where(CurrencyPair.symbol == symbol)
    )

    if not pair:
        raise HTTPException(404, "Unknown currency pair")

    ticks = db.scalars(
        select(PriceTick)
        .where(PriceTick.pair_id == pair.id)
        .order_by(PriceTick.id.desc())
        .limit(limit)
    ).all()

    return [
        {
            "mid": tick.mid,
            "bid": tick.bid,
            "ask": tick.ask,
            "recorded_at": tick.recorded_at,
        }
        for tick in reversed(ticks)
    ]


@app.post("/api/orders")
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
):
    pair = db.scalar(
        select(CurrencyPair).where(
            CurrencyPair.symbol == payload.symbol
        )
    )

    if pair is None:
        raise HTTPException(404, "Unknown currency pair")

    if payload.order_type == "LIMIT" and payload.limit_price is None:
        raise HTTPException(422, "limit_price is required for limit orders")

    order = Order(
        pair_id=pair.id,
        side=payload.side,
        order_type=payload.order_type,
        quantity=payload.quantity,
        limit_price=payload.limit_price,
        status="PENDING",
    )
    db.add(order)
    db.flush()

    fill_price = None

    if payload.order_type == "MARKET":
        fill_price = market_fill_price(pair, payload.side)
        fill_order(db, order, pair, fill_price)

    elif limit_is_marketable(pair, payload.side, payload.limit_price):
        fill_price = market_fill_price(pair, order.side)
        fill_order(db, order, pair, fill_price)

    db.commit()
    db.refresh(order)

    return {
        "id": order.id,
        "symbol": pair.symbol,
        "side": order.side,
        "order_type": order.order_type,
        "quantity": order.quantity,
        "limit_price": order.limit_price,
        "status": order.status,
        "fill_price": fill_price,
        "created_at": order.created_at,
    }


@app.get("/api/orders")
def orders(
    status: str | None = None,
    symbol: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    stmt = select(Order).join(CurrencyPair)

    if status:
        stmt = stmt.where(Order.status == status.upper())

    if symbol:
        stmt = stmt.where(CurrencyPair.symbol == symbol)

    rows = db.execute(
        stmt.order_by(Order.id.desc()).limit(
            min(max(limit, 1), 1000)
        )
    ).all()

    output = []

    for order, in rows:
        pair = db.get(CurrencyPair, order.pair_id)
        trade = db.scalar(
            select(Trade).where(Trade.order_id == order.id)
        )

        output.append(
            {
                "id": order.id,
                "symbol": pair.symbol,
                "side": order.side,
                "order_type": order.order_type,
                "quantity": order.quantity,
                "limit_price": order.limit_price,
                "status": order.status,
                "fill_price": trade.fill_price if trade else None,
                "created_at": order.created_at,
            }
        )

    return output


@app.get("/api/positions")
def positions(db: Session = Depends(get_db)):
    result = []

    for pos in db.scalars(select(Position)).all():
        pair = db.get(CurrencyPair, pos.pair_id)
        q = quote(pair)
        close_price = q["bid"] if pos.net_quantity > 0 else q["ask"]

        result.append(
            {
                "symbol": pair.symbol,
                "net_quantity": pos.net_quantity,
                "average_entry_price": pos.average_entry_price,
                "realized_pnl": pos.realized_pnl,
                "unrealized_pnl": unrealized_pnl(pos, close_price),
            }
        )

    return result


@app.get("/api/risk")
def risk(db: Session = Depends(get_db)):
    positions_data = positions(db)
    exposure = {}
    total_unrealized = Decimal("0")
    total_realized = Decimal("0")

    for position in positions_data:
        base, quote_currency = position["symbol"].split("/")
        base_exposure = Decimal(position["net_quantity"])
        quote_exposure = (
            -base_exposure * Decimal(position["average_entry_price"])
        )

        exposure[base] = exposure.get(base, Decimal("0")) + base_exposure
        exposure[quote_currency] = (
            exposure.get(quote_currency, Decimal("0")) + quote_exposure
        )

        total_unrealized += (
            Decimal(position["unrealized_pnl"])
            * fx_to_inr(position["symbol"], Decimal("1"))
        )
        total_realized += (
            Decimal(position["realized_pnl"])
            * fx_to_inr(position["symbol"], Decimal("1"))
        )

    snapshots = db.scalars(
        select(PortfolioSnapshot.equity_inr)
        .order_by(PortfolioSnapshot.id)
    ).all()

    curve = [Decimal(value) for value in snapshots]
    drawdown = max_drawdown(curve)

    return {
        "exposure": exposure,
        "realized_pnl_inr": total_realized,
        "unrealized_pnl_inr": total_unrealized,
        "total_pnl_inr": total_realized + total_unrealized,
        "max_drawdown_pct": drawdown * Decimal("100"),
    }


@app.get("/api/trades")
def trades(
    symbol: str | None = None,
    side: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    stmt = select(Trade).join(
        CurrencyPair,
        Trade.pair_id == CurrencyPair.id,
    )

    if symbol:
        stmt = stmt.where(CurrencyPair.symbol == symbol)

    if side:
        stmt = stmt.where(Trade.side == side.upper())

    rows = db.execute(
        stmt.order_by(Trade.id.desc()).limit(
            min(max(limit, 1), 1000)
        )
    ).all()

    return [
        {
            "id": trade.id,
            "order_id": trade.order_id,
            "symbol": db.get(CurrencyPair, trade.pair_id).symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "fill_price": trade.fill_price,
            "fee": trade.fee,
            "filled_at": trade.filled_at,
        }
        for (trade,) in rows
    ]


@app.websocket("/ws/prices")
async def price_socket(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            with SessionLocal() as db:
                payload = [
                    quote(pair)
                    for pair in db.scalars(
                        select(CurrencyPair)
                    ).all()
                ]

            await websocket.send_json(
                [
                    {
                        key: (
                            str(value)
                            if isinstance(value, Decimal)
                            else value.isoformat()
                            if isinstance(value, datetime)
                            else value
                        )
                        for key, value in item.items()
                    }
                    for item in payload
                ]
            )

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        return
