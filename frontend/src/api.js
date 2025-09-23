// frontend/src/api.js
export async function fetchCandles(symbol='XAUUSD', interval='5min', limit=200){
  const params = new URLSearchParams({ symbol, interval, limit });
  const resp = await fetch(`/ict/candles?${params.toString()}`);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Candles API error ${resp.status}: ${text}`);
  }
  const json = await resp.json();
  return json.candles || json;
}
