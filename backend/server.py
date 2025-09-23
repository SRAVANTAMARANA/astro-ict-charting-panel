import os
import json
import time
import asyncio
import datetime
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# --- ICT detectors ---
from detectors.fvg import detect_fvg
from detectors.liquidity import detect_liquidity
from detectors.turtle_soup import detect_turtle_soup
from detectors.market_structure import detect_market_structure
from detectors.signal_ranker import rank_signals

# --- API Keys ---
TWELVEDATA_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
API_TOKEN = os.getenv("API_TOKEN", "").strip()
PORT = int(os.getenv("PORT", "8000"))

BASE_DIR = os.path.dirname(__file__)
SIGNALS_FILE = os.path.join(BASE_DIR, "signals.json")

app = FastAPI(title="ICT Charting Backend")

# --- Models ---
class Candle(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0.0


# --- Fetch candles ---
async def fetch_twelvedata(symbol: str, interval: str, limit: int):
    if not TWELVEDATA_KEY:
        raise RuntimeError("No TwelveData key")
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": limit,
        "format": "JSON",
        "apikey": TWELVEDATA_KEY,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        j = r.json()
        if "values" not in j:
            raise RuntimeError(f"TwelveData error: {j}")
        vals = list(reversed(j["values"]))
        return [
            Candle(
                time=v["datetime"],
                open=float(v["open"]),
                high=float(v["high"]),
                low=float(v["low"]),
                close=float(v["close"]),
                volume=float(v.get("volume", 0.0)),
            )
            for v in vals[:limit]
        ]


async def fetch_finnhub(symbol: str, interval: str, limit: int):
    if not FINNHUB_KEY:
        raise RuntimeError("No Finnhub key")
    res_map = {"1min": "1", "5min": "5", "15min": "15", "30min": "30", "1h": "60", "1d": "D"}
    resolution = res_map.get(interval, "1")
    now = int(time.time())
    start = now - (limit + 10) * 60
    url = "https://finnhub.io/api/v1/stock/candle"
    params = {"symbol": symbol, "resolution": resolution, "from": start, "to": now, "token": FINNHUB_KEY}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        j = r.json()
        if j.get("s") != "ok":
            raise RuntimeError(f"Finnhub error: {j}")
        return [
            Candle(
                time=datetime.datetime.utcfromtimestamp(t).isoformat() + "Z",
                open=float(j["o"][i]),
                high=float(j["h"][i]),
                low=float(j["l"][i]),
                close=float(j["c"][i]),
                volume=float(j["v"][i]) if "v" in j else 0.0,
            )
            for i, t in enumerate(j["t"][:limit])
        ]


def synthetic_candles(symbol: str, interval: str, limit: int):
    now = datetime.datetime.utcnow()
    candles = []
    price = 100.0
    step = 0.1
    for i in range(limit):
        t = now - datetime.timedelta(minutes=(limit - i))
        o = price + (i % 5 - 2) * step
        c = o + (-1) ** i * step
        h = max(o, c) + step / 2
        l = min(o, c) - step / 2
        candles.append(
            Candle(
                time=t.isoformat() + "Z",
                open=round(o, 6),
                high=round(h, 6),
                low=round(l, 6),
                close=round(c, 6),
                volume=100 + i,
            )
        )
        price = c
    return candles


# --- Detector runner ---
def run_detectors(symbol: str, candles: List[Candle]) -> List[Dict[str, Any]]:
    data = [c.dict() for c in candles]
    signals = []
    signals += detect_liquidity(data)
    signals += detect_turtle_soup(data)
    signals += detect_fvg(data)
    signals += detect_market_structure(data)
    for s in signals:
        s.setdefault("symbol", symbol)
        s.setdefault("time", data[-1]["time"])
    ranked = rank_signals(signals)
    with open(SIGNALS_FILE, "w") as f:
        json.dump(ranked, f, indent=2)
    return ranked


# --- Endpoints ---
@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat() + "Z"}


@app.get("/ict/candles")
async def get_candles(symbol: str = Query("XAUUSD"), interval: str = Query("1min"), limit: int = Query(200)):
    try:
        if TWELVEDATA_KEY:
            return {"symbol": symbol, "candles": [c.dict() for c in await fetch_twelvedata(symbol, interval, limit)]}
    except Exception:
        pass
    try:
        if FINNHUB_KEY:
            return {"symbol": symbol, "candles": [c.dict() for c in await fetch_finnhub(symbol, interval, limit)]}
    except Exception:
        pass
    return {"symbol": symbol, "candles": [c.dict() for c in synthetic_candles(symbol, interval, limit)], "note": "synthetic"}


@app.get("/signals")
async def get_signals():
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE) as f:
            return {"signals": json.load(f)}
    return {"signals": []}


@app.post("/run-detect")
async def run_detect(symbol: str = Query("XAUUSD"), interval: str = Query("1min"), limit: int = Query(200)):
    res = await get_candles(symbol, interval, limit)
    candles = [Candle(**c) for c in res["candles"]]
    signals = run_detectors(symbol, candles)
    return {"status": "ok", "signals": signals}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True)
