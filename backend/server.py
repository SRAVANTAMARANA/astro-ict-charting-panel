# backend/server.py
import os
import time
import logging
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

TWELVEDATA_KEY = os.getenv("TWELVEDATA_KEY", "").strip()
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "").strip()

app = FastAPI(title="ICT Charting Backend")
logging.basicConfig(level=logging.INFO)

# allow the frontend (same host via nginx) - for dev you can set origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class Candle(BaseModel):
    time: str   # ISO string or epoch seconds
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0

def _td_interval_map(interval: str) -> str:
    # TwelveData interval mapping - keep same for common intervals
    return interval

async def fetch_from_twelvedata(symbol: str, interval: str, limit: int = 200):
    if not TWELVEDATA_KEY:
        raise RuntimeError("TWELVEDATA_KEY not configured")
    # twelve data time_series endpoint
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": _td_interval_map(interval),
        "outputsize": limit,
        "format": "JSON",
        "apikey": TWELVEDATA_KEY,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"twdata status {r.status_code}")
        j = r.json()
        if "values" not in j:
            raise RuntimeError(f"TwelveData unexpected: {j}")
        vals = j["values"]
        # TwelveData returns newest first; reverse to chronological oldest->newest
        vals = list(reversed(vals))
        out = []
        for v in vals:
            # time may be '2025-09-23 16:00:00' ; convert to ISO date/time
            out.append({
                "time": v.get("datetime") or v.get("timestamp") or v.get("date") or v.get("time"),
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
                "volume": float(v.get("volume") or 0),
            })
        return out

async def fetch_from_finnhub(symbol: str, interval: str, limit: int = 200):
    if not FINNHUB_KEY:
        raise RuntimeError("FINNHUB_KEY not configured")
    # Simplified mapping and sampling - Finnhub requires from/to timestamps. We will fetch a reasonable window.
    # Provide minute/5min/hour/day mapping roughly
    now = int(time.time())
    multiplier = {
        "1min": 60, "5min": 60*5, "15min": 60*15,
        "1h": 60*60, "1d": 60*60*24
    }.get(interval, 60*5)
    # fetch last limit * multiplier seconds
    _from = now - multiplier * limit
    url = "https://finnhub.io/api/v1/stock/candle"
    params = {"symbol": symbol, "resolution": {
        "1min":"1", "5min":"5", "15min":"15","1h":"60","1d":"D"
    }.get(interval, "5"), "from": _from, "to": now, "token": FINNHUB_KEY}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"finnhub status {r.status_code}")
        j = r.json()
        if j.get("s") != "ok":
            raise RuntimeError(f"finnhub error: {j}")
        t = j["t"]
        c = j["c"]
        o = j["o"]
        h = j["h"]
        l = j["l"]
        v = j.get("v", [0]*len(t))
        out = []
        for i in range(len(t)):
            out.append({
                "time": int(t[i]),
                "open": float(o[i]),
                "high": float(h[i]),
                "low": float(l[i]),
                "close": float(c[i]),
                "volume": float(v[i] if i < len(v) else 0)
            })
        return out

@app.get("/ict/health")
async def health():
    return {"status":"ok", "time": int(time.time())}

@app.get("/ict/candles")
async def get_candles(
    symbol: str = Query(..., min_length=1),
    interval: str = Query("5min"),
    limit: int = Query(200, ge=1, le=1000)
):
    symbol = symbol.strip().upper()
    # Try TwelveData first, then Finnhub fallback
    errors = []
    try:
        data = await fetch_from_twelvedata(symbol, interval, limit)
        return JSONResponse({"candles": data})
    except Exception as e:
        errors.append(f"td:{e}")
    try:
        data = await fetch_from_finnhub(symbol, interval, limit)
        return JSONResponse({"candles": data})
    except Exception as e:
        errors.append(f"fh:{e}")
    raise HTTPException(status_code=502, detail={"message":"no provider available", "errors": errors})
