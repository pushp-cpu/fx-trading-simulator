# FX Trading Simulator

A full-stack, educational foreign-exchange trading simulator. It uses geometric Brownian motion (GBM) to simulate prices for USD/INR, EUR/USD, GBP/USD, USD/JPY, and EUR/INR. It is not connected to a broker and does not use real market prices.

## Features
- Per-pair drift, volatility and bid/ask spread.
- One-second GBM price updates in a FastAPI background task.
- Market orders and persistent limit orders.
- Average-cost position accounting with partial closes and long/short flips.
- Realized and mark-to-market unrealized P&L.
- Currency exposure, portfolio P&L and maximum drawdown estimate.
- Filterable executed-trade blotter and price history.
- Next.js dashboard, WebSocket price ticker, and polling fallback.
- 20+ pytest tests for accounting, drawdown, GBM validation and order matching.

## Architecture

```mermaid
flowchart TD
  UI[Next.js + React + TypeScript] <-->|REST + WebSocket| API[FastAPI]
  API --> PE[GBM Price Engine]
  API --> OM[Order Matching]
  API --> PA[Position Accounting]
  API --> RE[Risk and Portfolio]
  PE --> DB[(PostgreSQL)]
  OM --> DB
  PA --> DB
  RE --> DB
```

## GBM formula

`S(t + dt) = S(t) * exp((mu - sigma^2 / 2) * dt + sigma * sqrt(dt) * Z)`

- `S`: mid price
- `mu`: annualized drift
- `sigma`: annualized volatility
- `dt`: elapsed time in years
- `Z`: standard normal random variable

The one-second update uses `dt = 1 / (365.25 * 24 * 60 * 60)`. Python floating point is used for the stochastic exponential; trading quantities and prices are represented as `Decimal` at the accounting/API boundary.

## Quick start on Windows (one setup script)

Open PowerShell in the extracted project folder and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\\setup.ps1
```

If Docker Desktop is running, the script builds and starts the full stack with Docker Compose. If Docker is unavailable, it uses a running local PostgreSQL service, asks for the local PostgreSQL password without echoing it, creates an isolated `fxsim` database, installs Python and npm dependencies, runs tests, and launches the backend/frontend in separate terminals.

Requirements for the local fallback: Python 3.11+, Node.js 20+, and PostgreSQL. The local database is named `fxsim` and does not touch any other project database.

## Quick start with Docker Compose

Requirements: Docker Desktop with Compose enabled.

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Swagger API: http://localhost:8000/docs
- Health check: http://localhost:8000/health

PostgreSQL is mapped to host port 5434 to avoid colliding with a local PostgreSQL service. The backend connects to the Compose service internally on port 5432.

Stop the stack with `Ctrl+C`, then `docker compose down`. To also delete demo data, run `docker compose down -v`.

## Run tests locally

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

The backend needs a PostgreSQL database for API operation. Set `DATABASE_URL` before running it. For example, from the repository root with Docker database running:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://fxuser:fxpassword@localhost:5434/fxsim"
uvicorn app.main:app --app-dir backend --reload
```

Run the frontend locally in another terminal:

```bash
cd frontend
npm install
# copy .env.local.example to .env.local if you need custom API URLs
npm run dev
```

## API overview
- `GET /health`
- `GET /api/prices`
- `GET /api/prices/history?symbol=USD%2FINR&limit=60`
- `POST /api/orders`
- `GET /api/orders?status=PENDING&symbol=USD%2FINR`
- `GET /api/positions`
- `GET /api/risk`
- `GET /api/trades?symbol=USD%2FINR&side=BUY`
- `WS /ws/prices`

Example market order:

```json
{
  "symbol": "EUR/USD",
  "side": "BUY",
  "order_type": "MARKET",
  "quantity": "1000"
}
```

Example limit order:

```json
{
  "symbol": "USD/INR",
  "side": "BUY",
  "order_type": "LIMIT",
  "quantity": "1000",
  "limit_price": "82.50"
}
```

Limit buys fill when ask <= limit; limit sells fill when bid >= limit. Pending limit orders are checked each time a simulated price tick is processed.

## Deployment guide

### Database on Neon
1. Create a PostgreSQL project on Neon.
2. Copy the connection string and use SQLAlchemy's psycopg URL format, for example `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`.
3. Set `DATABASE_URL` in Render. Never commit credentials.

### Backend on Render
1. Create a new Web Service from the GitHub repository.
2. Set root directory to `backend`.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add `DATABASE_URL` and `TICK_INTERVAL_SECONDS=1` environment variables.
6. Add your Vercel frontend origin to CORS in `app/main.py` before deployment. The current allowlist is for local development.

### Frontend on Vercel
1. Import the repository into Vercel.
2. Set root directory to `frontend`.
3. Set `NEXT_PUBLIC_API_URL` to the Render backend HTTPS URL.
4. Set `NEXT_PUBLIC_WS_URL` to the backend WebSocket URL using `wss://.../ws/prices`.
5. Deploy and verify browser networking/CORS.

## Dashboard preview

This design preview illustrates the intended dashboard layout; it is not a screenshot from a running instance. After launching the app, replace it with a real screenshot from `http://localhost:3000`.

![FX Trading Simulator dashboard design preview](docs/dashboard-preview.svg)


## Accounting rules and assumptions
- Market buy fills at ask; market sell fills at bid.
- Unrealized P&L is calculated at the executable close side (bid for long, ask for short).
- Position quantity is expressed in base currency; per-pair P&L is in quote currency.
- The demo uses illustrative conversion factors for non-INR quote currencies. For production-quality portfolio INR P&L, use a complete, timestamped FX conversion graph and a rigorously defined cash/margin ledger.
- This educational prototype does not model margin, financing, swap points, transaction fees beyond a zero fee field, authentication, multi-user isolation, order cancellation, or exchange outages. A single in-process background task is appropriate for a local demo, not horizontally scaled deployment without a single-leader/worker strategy.
- GBM parameters are illustrative and are not forecasts or investment advice.

## 10 interview questions and short answers

1. **Why GBM?** It is a simple stochastic process that keeps simulated prices positive and models proportional returns.
2. **Why use Decimal for accounting?** Decimal avoids common binary floating-point rounding artifacts in financial calculations.
3. **Why separate pricing and matching?** Price generation and order execution have different responsibilities and can be tested independently.
4. **What is the bid/ask spread?** Bid is the sell-side quote and ask is the buy-side quote; the difference represents a simulated transaction cost.
5. **How is average entry calculated?** Add same-direction exposure using a quantity-weighted average; preserve the entry price for the remaining quantity when partially closing.
6. **How is realized P&L calculated?** Closed quantity multiplied by the price difference, with sign based on whether the old position was long or short.
7. **How does a position flip work?** Close the existing side first, realize P&L on the closed size, then set the excess opposite-side position's entry to the flip fill.
8. **How do limit orders fill?** Buy limits fill when ask is at or below the limit; sell limits fill when bid is at or above the limit.
9. **What is maximum drawdown?** The largest percentage fall from a previous equity peak to a later observed value.
10. **What would production require?** Authentication, account isolation, robust ledger/currency conversion, concurrency controls, observability, data retention, risk limits, and a coordinated price worker.

## License
Educational use. No financial advice or live execution.
