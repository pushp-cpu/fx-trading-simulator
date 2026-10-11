"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, ArrowDownLeft, ArrowUpRight, CircleDollarSign, RefreshCw, Wifi } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API, WS, getJson, type Price, type Position } from "@/lib/api";

type Trade = { id: number; symbol: string; side: string; quantity: string; fill_price: string; filled_at: string };
type Order = { id: number; symbol: string; side: string; order_type: string; quantity: string; status: string; fill_price: string | null; created_at: string };
type Risk = { total_pnl_inr: string; realized_pnl_inr: string; unrealized_pnl_inr: string; max_drawdown_pct: string; exposure: Record<string,string> };
type Tick = { mid: number; recorded_at: string };

const money = (v: string | number, digits=2) => Number(v).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
export default function Home() {
  const [prices, setPrices] = useState<Price[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [risk, setRisk] = useState<Risk | null>(null);
  const [history, setHistory] = useState<Tick[]>([]);
  const [selected, setSelected] = useState("USD/INR");
  const [side, setSide] = useState<"BUY"|"SELL">("BUY");
  const [type, setType] = useState<"MARKET"|"LIMIT">("MARKET");
  const [quantity, setQuantity] = useState("1000");
  const [limit, setLimit] = useState("");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [sideFilter, setSideFilter] = useState("");
  const [message, setMessage] = useState("");
  const [online, setOnline] = useState(false);
  const selectedPrice = prices.find(p => p.symbol === selected);
  const refresh = useCallback(async () => {
    try {
      const [p, pos, t, o, r, h] = await Promise.all([
        getJson<Price[]>("/api/prices"), getJson<Position[]>("/api/positions"),
        getJson<Trade[]>("/api/trades"), getJson<Order[]>("/api/orders"),
        getJson<Risk>("/api/risk"), getJson<Tick[]>(`/api/prices/history?symbol=${encodeURIComponent(selected)}&limit=60`)
      ]);
      setPrices(p); setPositions(pos); setTrades(t); setOrders(o); setRisk(r);
      setHistory(h.map(x => ({...x, mid:Number(x.mid)})));
    } catch { setMessage("API unavailable — start the backend on port 8000."); }
  }, [selected]);
  useEffect(() => {
    void refresh();
    const interval = setInterval(() => { void refresh(); }, 2500);
    let socket: WebSocket | undefined;
    try {
      socket = new WebSocket(WS);
      socket.onopen = () => setOnline(true);
      socket.onclose = () => setOnline(false);
      socket.onmessage = event => { try { setPrices(JSON.parse(event.data)); } catch {} };
    } catch { setOnline(false); }
    return () => { clearInterval(interval); socket?.close(); };
  }, [refresh]);
  const submit = async () => {
    setMessage("");
    try {
      const response = await fetch(`${API}/api/orders`, { method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({symbol:selected, side, order_type:type, quantity, limit_price:type==="LIMIT" ? limit : null}) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Order rejected");
      setMessage(`Order #${data.id}: ${data.status}${data.fill_price ? ` at ${data.fill_price}` : ""}`);
      await refresh();
    } catch(e) { setMessage(e instanceof Error ? e.message : "Could not place order"); }
  };
  const chartData = useMemo(() => history.map((h,i) => ({ time: new Date(h.recorded_at).toLocaleTimeString(), mid: h.mid, index:i })), [history]);
  const filteredTrades = trades.filter(t => (!symbolFilter || t.symbol===symbolFilter) && (!sideFilter || t.side===sideFilter));
  return <main className="mx-auto max-w-[1500px] p-4 md:p-7">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3"><div className="rounded-xl bg-mint/10 p-3 text-mint"><Activity size={26}/></div><div><p className="text-xs font-semibold uppercase tracking-[.25em] text-mint">SIMULATION ENVIRONMENT</p><h1 className="text-2xl font-bold md:text-3xl">FX Trading Desk</h1><p className="muted mt-1 text-sm">Live simulated markets · No real money</p></div></div>
      <div className="flex items-center gap-2 rounded-full border border-line px-3 py-2 text-sm"><span className={`h-2 w-2 rounded-full ${online?"bg-mint":"bg-amber-400"}`}/><Wifi size={15}/>{online?"WebSocket live":"Polling fallback"}</div>
    </header>
    <section className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {prices.map(p=><button key={p.symbol} onClick={()=>setSelected(p.symbol)} className={`panel p-4 text-left ${selected===p.symbol?"border-mint/70":""}`}><div className="flex justify-between text-sm font-semibold">{p.symbol}<span className="muted text-xs">FX</span></div><div className="mt-3 text-2xl font-semibold tabular-nums">{money(p.mid, p.symbol.includes("JPY")?3:4)}</div><div className="mt-2 flex justify-between text-xs muted"><span>Bid {money(p.bid,4)}</span><span>Ask {money(p.ask,4)}</span></div></button>)}
    </section>
    <section className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
      {[["Portfolio P&L",risk?.total_pnl_inr],["Realized P&L",risk?.realized_pnl_inr],["Unrealized P&L",risk?.unrealized_pnl_inr],["Max drawdown",risk?.max_drawdown_pct]].map(([label,value])=><div key={label} className="panel p-4"><p className="muted text-sm">{label}</p><p className={`mt-2 text-2xl font-bold ${Number(value||0)>=0?"text-mint":"text-rose-400"}`}>{value===undefined?"—":label==="Max drawdown"?`${money(value)}%`:`₹${money(value)}`}</p></div>)}
    </section>
    <section className="mb-5 grid grid-cols-1 gap-5 xl:grid-cols-[1.7fr_1fr]">
      <div className="panel p-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="font-semibold">{selected} price</h2><p className="muted mt-1 text-sm">Simulated mid-price · recent ticks</p></div><span className="rounded-lg bg-mint/10 p-2 text-mint"><RefreshCw size={17}/></span></div>
        <div className="h-[270px] w-full">{chartData.length>1?<ResponsiveContainer width="100%" height="100%"><LineChart data={chartData}><CartesianGrid stroke="#25344a" strokeDasharray="3 3"/><XAxis dataKey="time" tick={{fill:"#91a3bb",fontSize:10}} minTickGap={40}/><YAxis domain={["auto","auto"]} tick={{fill:"#91a3bb",fontSize:10}} width={75}/><Tooltip contentStyle={{background:"#111c2e",border:"1px solid #25344a",borderRadius:10}}/><Line type="monotone" dataKey="mid" stroke="#4de2b1" dot={false} strokeWidth={2} isAnimationActive={false}/></LineChart></ResponsiveContainer>:<div className="muted flex h-full items-center justify-center">Collecting price ticks…</div>}</div>
      </div>
      <div className="panel p-5"><h2 className="mb-1 font-semibold">Place an order</h2><p className="muted mb-5 text-sm">Simulated execution with bid/ask spread</p>
        <div className="mb-4 grid grid-cols-2 gap-2"><button onClick={()=>setSide("BUY")} className={`rounded-lg py-3 font-semibold ${side==="BUY"?"bg-mint text-ink":"bg-[#0b1423] text-slate-300"}`}><ArrowUpRight className="mr-1 inline" size={17}/>Buy</button><button onClick={()=>setSide("SELL")} className={`rounded-lg py-3 font-semibold ${side==="SELL"?"bg-rose-500 text-white":"bg-[#0b1423] text-slate-300"}`}><ArrowDownLeft className="mr-1 inline" size={17}/>Sell</button></div>
        <label className="mb-1 block text-xs muted">Currency pair</label><select value={selected} onChange={e=>setSelected(e.target.value)} className="mb-3">{prices.map(p=><option key={p.symbol}>{p.symbol}</option>)}</select>
        <label className="mb-1 block text-xs muted">Order type</label><select value={type} onChange={e=>setType(e.target.value as "MARKET"|"LIMIT")} className="mb-3"><option value="MARKET">Market</option><option value="LIMIT">Limit</option></select>
        <label className="mb-1 block text-xs muted">Quantity (base currency)</label><input type="number" min="0.0001" step="0.0001" value={quantity} onChange={e=>setQuantity(e.target.value)} className="mb-3"/>
        {type==="LIMIT"&&<><label className="mb-1 block text-xs muted">Limit price</label><input type="number" min="0.00000001" step="0.00000001" value={limit} onChange={e=>setLimit(e.target.value)} className="mb-3" placeholder="Enter limit price"/></>}
        <button disabled={!selectedPrice||Number(quantity)<=0||(type==="LIMIT"&&Number(limit)<=0)} onClick={()=>void submit()} className={`mt-2 w-full rounded-lg py-3 font-bold ${side==="BUY"?"bg-mint text-ink":"bg-rose-500 text-white"}`}>Submit {side} order</button>
        {message&&<p className="mt-3 rounded-lg bg-[#0b1423] p-3 text-sm">{message}</p>}
        {selectedPrice&&<p className="muted mt-3 text-xs">Bid {selectedPrice.bid} · Ask {selectedPrice.ask}</p>}
      </div>
    </section>
    <section className="mb-5 grid grid-cols-1 gap-5 xl:grid-cols-2">
      <div className="panel overflow-hidden p-4"><h2 className="mb-3 flex items-center gap-2 font-semibold"><CircleDollarSign size={18} className="text-mint"/>Open positions</h2><div className="overflow-x-auto"><table><thead><tr><th>Pair</th><th>Net qty</th><th>Avg entry</th><th>Realized</th><th>Unrealized</th></tr></thead><tbody>{positions.filter(p=>Number(p.net_quantity)!==0).map(p=><tr key={p.symbol}><td>{p.symbol}</td><td>{money(p.net_quantity,4)}</td><td>{money(p.average_entry_price,5)}</td><td>{money(p.realized_pnl)}</td><td className={Number(p.unrealized_pnl)>=0?"text-mint":"text-rose-400"}>{money(p.unrealized_pnl)}</td></tr>)}{positions.filter(p=>Number(p.net_quantity)!==0).length===0&&<tr><td colSpan={5} className="muted py-8 text-center">No open positions yet. Place a market order to begin.</td></tr>}</tbody></table></div></div>
      <div className="panel overflow-hidden p-4"><h2 className="mb-3 font-semibold">Pending & recent orders</h2><div className="overflow-x-auto"><table><thead><tr><th>ID</th><th>Pair</th><th>Side</th><th>Type</th><th>Qty</th><th>Status</th></tr></thead><tbody>{orders.slice(0,8).map(o=><tr key={o.id}><td>#{o.id}</td><td>{o.symbol}</td><td className={o.side==="BUY"?"text-mint":"text-rose-400"}>{o.side}</td><td>{o.order_type}</td><td>{money(o.quantity,2)}</td><td>{o.status}</td></tr>)}{orders.length===0&&<tr><td colSpan={6} className="muted py-8 text-center">No orders yet.</td></tr>}</tbody></table></div></div>
    </section>
    <section className="panel overflow-hidden p-4"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Trade blotter</h2><p className="muted mt-1 text-sm">Executed trades · newest first</p></div><div className="flex gap-2"><select className="min-w-32" value={symbolFilter} onChange={e=>setSymbolFilter(e.target.value)}><option value="">All pairs</option>{prices.map(p=><option key={p.symbol}>{p.symbol}</option>)}</select><select className="min-w-24" value={sideFilter} onChange={e=>setSideFilter(e.target.value)}><option value="">All sides</option><option>BUY</option><option>SELL</option></select></div></div><div className="overflow-x-auto"><table><thead><tr><th>Trade ID</th><th>Pair</th><th>Side</th><th>Quantity</th><th>Fill price</th><th>Time</th></tr></thead><tbody>{filteredTrades.slice(0,30).map(t=><tr key={t.id}><td>#{t.id}</td><td>{t.symbol}</td><td className={t.side==="BUY"?"text-mint":"text-rose-400"}>{t.side}</td><td>{money(t.quantity,4)}</td><td>{money(t.fill_price,5)}</td><td>{new Date(t.filled_at).toLocaleTimeString()}</td></tr>)}{filteredTrades.length===0&&<tr><td colSpan={6} className="muted py-8 text-center">No trades match the filters.</td></tr>}</tbody></table></div></section>
    <footer className="muted mt-6 flex flex-wrap justify-between gap-2 text-xs"><span>FX Trading Simulator · Educational use only · No live broker connection</span><span>GBM prices are stochastic simulations, not market forecasts.</span></footer>
  </main>;
}
