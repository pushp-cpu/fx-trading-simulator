export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const WS = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/prices";
export type Price = { symbol: string; mid: string; bid: string; ask: string; updated_at: string };
export type Position = { symbol: string; net_quantity: string; average_entry_price: string; realized_pnl: string; unrealized_pnl: string };
export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
