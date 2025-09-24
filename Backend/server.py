# FastAPI backend: proxies /ict/time_series and /ict/health
import os
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # will read .env in container

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
ALPHA_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")
TWELVE_KEY = os.getenv("TWELVEDATA_API_KEY", "")

app = FastAPI(title="ASTRA ICT Proxy")

# allow frontend to call (from localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in production restrict
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ict/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}

# helper: convert interval string to seconds & to API resolution
INTERVAL_TO_RES = {
    "1m": {"finn": "1", "av": "1min", "td": "1min"},
    "5m": {"finn": "5", "av": "5min", "td": "5min"},
    "15m": {"finn": "15", "av": "15min", "td": "15min"},
    "30m": {"finn": "30", "av": "30min", "td": "30min"},
    "1h": {"finn": "60", "av": "60min", "td": "1h"},
    "4h": {"finn": "240", "av": "60min", "td": "4h"},
    "1d": {"finn": "D", "av": "daily", "td": "1day"},
}

def unix_seconds(dt: datetime) -> int:
    return int(dt.timestamp())

async def fetch_finnhub(symbol: str, interval: str):
    if not FINNHUB_KEY:
        raise RuntimeError("no finnhub key")
    resmap = INTERVAL_TO_RES.get(interval, INTERVAL_TO_RES["1m"])
    resolution = resmap["finn"]
    to_ts = unix_seconds(datetime.utcnow())
    from_ts = to_ts - 60 * 60 * 6  # 6 hours default window for intraday
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution={resolution}&from={from_ts}&to={to_ts}&token={FINNHUB_KEY}"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
    if data.get("s") != "ok":
        raise RuntimeError("finnhub returned not ok")
    # convert to unified format
    return {
        "source": "finnhub",
        "c": data["c"],
        "h": data["h"],
        "l": data["l"],
        "o": data["o"],
        "t": data["t"],
        "v": data.get("v", []),
    }

async def fetch_alphavantage(symbol: str, interval: str):
    if not ALPHA_KEY:
        raise RuntimeError("no alphavantage key")
    resmap = INTERVAL_TO_RES.get(interval, INTERVAL_TO_RES["1m"])
    av_interval = resmap["av"]
    # For simplicity use TIME_SERIES_INTRADAY for intraday; daily for daily
    if av_interval.endswith("min"):
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={av_interval}&outputsize=compact&apikey={ALPHA_KEY}"
    else:
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=compact&apikey={ALPHA_KEY}"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
    # Alphavantage returns keys with naming; try to parse
    ts_key = None
    for k in data.keys():
        if "Time Series" in k:
            ts_key = k
            break
    if not ts_key:
        raise RuntimeError("alpha: no timeseries")
    timeseries = data[ts_key]
    # convert to arrays (sorted by time asc)
    times = sorted(timeseries.keys())
    o,h,l,c,v = [],[],[],[],[]
    t_unix=[]
    for tm in times:
        item = timeseries[tm]
        o.append(float(item["1. open"]))
        h.append(float(item["2. high"]))
        l.append(float(item["3. low"]))
        c.append(float(item["4. close"]))
        v.append(float(item.get("5. volume", 0)))
        # convert to unix seconds
        dt = datetime.fromisoformat(tm)
        t_unix.append(unix_seconds(dt))
    return {"source":"alphavantage","o":o,"h":h,"l":l,"c":c,"v":v,"t":t_unix}

async def fetch_twelvedata(symbol: str, interval: str):
    if not TWELVE_KEY:
        raise RuntimeError("no twelvedata key")
    resmap = INTERVAL_TO_RES.get(interval, INTERVAL_TO_RES["1m"])
    td_interval = resmap["td"]
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={td_interval}&outputsize=500&apikey={TWELVE_KEY}"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
    if "status" in data and data["status"] != "ok":
        raise RuntimeError("twelvedata not ok")
    values = data.get("values", [])
    # TwelveData returns newest-first; we convert to oldest-first
    values = list(reversed(values))
    o,h,l,c,t_unix,v = [],[],[],[],[],[]
    for vitem in values:
        o.append(float(vitem["open"]))
        h.append(float(vitem["high"]))
        l.append(float(vitem["low"]))
        c.append(float(vitem["close"]))
        v.append(float(vitem.get("volume", 0) or 0))
        # convert time to unix
        # TwelveData time usually like '2025-09-24 14:35:00'
        tstr = vitem.get("datetime") or vitem.get("timestamp") or vitem.get("datetime_utc")
        try:
            dt = datetime.fromisoformat(tstr)
            t_unix.append(unix_seconds(dt))
        except Exception:
            try:
                t_unix.append(int(vitem.get("timestamp")))
            except:
                t_unix.append(unix_seconds(datetime.utcnow()))
    return {"source":"twelvedata","o":o,"h":h,"l":l,"c":c,"v":v,"t":t_unix}

@app.get("/ict/time_series")
async def time_series(
    symbol: str = Query(..., example="AAPL"),
    interval: str = Query("1m", example="1m"),
):
    symbol = symbol.upper()
    errors=[]
    # try finnhub first
    try:
        data = await fetch_finnhub(symbol, interval)
        return JSONResponse(content={"ok": True, "data": data})
    except Exception as e:
        errors.append(f"finnhub:{str(e)}")
    # then alphavantage
    try:
        data = await fetch_alphavantage(symbol, interval)
        return JSONResponse(content={"ok": True, "data": data})
    except Exception as e:
        errors.append(f"alpha:{str(e)}")
    # then twelvedata
    try:
        data = await fetch_twelvedata(symbol, interval)
        return JSONResponse(content={"ok": True, "data": data})
    except Exception as e:
        errors.append(f"twelve:{str(e)}")
    return JSONResponse(status_code=500, content={"ok": False, "errors": errors})
