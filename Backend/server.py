# Backend/server.py
import os
import asyncio
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TWELVE_KEY = os.getenv("TWELVEDATA_APIKEY", "").strip()
FINNHUB_KEY = os.getenv("FINNHUB_APIKEY", "").strip()
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "200"))

app = FastAPI(title="ICT Charting Panel Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to frontend origin in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ict/health")
async def health():
    return {"status":"ok", "time": datetime.utcnow().isoformat() + "Z"}

class Candle(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

@app.get("/ict/candles")
async def get_candles(symbol: str = Query(...), interval: str = Query("1min"), limit: int = Query(DEFAULT_LIMIT)):
    """
    Returns:
      { "symbol": "...", "candles": [ {time, open, high, low, close, volume}, ... ] }
    The backend tries TwelveData first, then Finnhub if TwelveData fails.
    """
    # Normalize symbol for TwelveData if needed (they usually expect "AAPL" or "XAUUSD")
    # Map interval to TwelveData format (if user uses 1m/5m vs 1min/5min)
    interval_map = {
        "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "60m": "60min",
        "1min":"1min","5min":"5min","15min":"15min","60min":"60min","1h":"60min","1d":"1day","1day":"1day"
    }
    td_interval = interval_map.get(interval, interval)

    # Try TwelveData
    if TWELVE_KEY:
        try:
            url = "https://api.twelvedata.com/time_series"
            params = {
                "apikey": TWELVE_KEY,
                "symbol": symbol,
                "interval": td_interval,
                "outputsize": limit,
                "format": "JSON"
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url, params=params)
                data = r.json()
                if r.status_code == 200 and "values" in data:
                    values = data["values"]
                    # TwelveData returns most recent first. Reverse so older->newer
                    values = list(reversed(values))[:limit]
                    candles = []
                    for v in values:
                        # time format: "2025-09-24 12:31:00" -> convert to ISO
                        t = v.get("datetime") or v.get("datetime")
                        # Try to normalize exactly to ISO with Z
                        try:
                            parsed = datetime.fromisoformat(t) if "T" in t else datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
                            t_iso = parsed.isoformat() + "Z"
                        except Exception:
                            t_iso = t
                        candles.append({
                            "time": t_iso,
                            "open": float(v.get("open", 0)),
                            "high": float(v.get("high", 0)),
                            "low": float(v.get("low", 0)),
                            "close": float(v.get("close", 0)),
                            "volume": float(v.get("volume", 0)) if v.get("volume") is not None else None
                        })
                    return {"symbol": symbol, "candles": candles}
                else:
                    # log small reason and fallthrough
                    # If TwelveData returns code != 200 or missing values -> fallback
                    pass
        except Exception as e:
            # network or parsing error -> try fallback
            pass

    # Fallback to Finnhub (requires FINNHUB_KEY)
    if FINNHUB_KEY:
        try:
            # Finnhub kline endpoint expects resolution like 1,5,15,60,D
            res_map = {
                "1min":"1", "5min":"5", "15min":"15", "30min":"30", "60min":"60",
                "1h":"60", "1d":"D", "1day":"D"
            }
            resolution = res_map.get(interval, "1")
            to_ts = int(datetime.utcnow().timestamp())
            # We'll request enough candles: limit * approximate seconds
            # Finnhub requires from/to timestamps
            # For simplicity request last 30 days as fallback (coarse)
            from_ts = to_ts - (limit * 60 * 2)  # conservative
            url = "https://finnhub.io/api/v1/stock/candle"
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "from": from_ts,
                "to": to_ts,
                "token": FINNHUB_KEY
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url, params=params)
                data = r.json()
                if r.status_code == 200 and data.get("s") == "ok":
                    # arrays: t, o, h, l, c, v
                    t_arr = data.get("t", [])
                    o_arr = data.get("o", [])
                    h_arr = data.get("h", [])
                    l_arr = data.get("l", [])
                    c_arr = data.get("c", [])
                    v_arr = data.get("v", [])
                    candles = []
                    for i in range(min(len(t_arr), limit)):
                        ts = int(t_arr[i])
                        iso = datetime.utcfromtimestamp(ts).isoformat() + "Z"
                        candles.append({
                            "time": iso,
                            "open": float(o_arr[i]),
                            "high": float(h_arr[i]),
                            "low": float(l_arr[i]),
                            "close": float(c_arr[i]),
                            "volume": float(v_arr[i]) if i < len(v_arr) else None
                        })
                    return {"symbol": symbol, "candles": candles}
        except Exception:
            pass

    # If both fail, raise 502
    raise HTTPException(status_code=502, detail="Failed to fetch candles from upstream APIs")
