# backend/server.py
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from dotenv import load_dotenv

load_dotenv()

TWELVE_APIKEY = os.getenv("TWELVEDATA_APIKEY") or os.environ.get("TWELVEDATA_APIKEY")
FINNHUB_KEY = os.getenv("FINNHUB_KEY") or os.environ.get("FINNHUB_KEY")

app = FastAPI(title="ICT Charting Backend")

# Allow all origins during dev; lock this down for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET","POST","OPTIONS"],
    allow_headers=["*"],
)

@app.get("/ict/health")
async def health():
    return {"status": "ok"}

@app.get("/api/time_series")
async def time_series(symbol: str = Query(...), interval: str = Query("1min")):
    """
    Proxy to TwelveData time_series endpoint. Example:
    /api/time_series?symbol=AAPL&interval=1min
    """
    if not TWELVE_APIKEY:
        raise HTTPException(status_code=500, detail="Server missing TWELVEDATA_APIKEY")
    url = "https://api.twelvedata.com/time_series"
    params = {"symbol": symbol, "interval": interval, "apikey": TWELVE_APIKEY, "outputsize": 100}
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params)
    try:
        j = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Bad response from TwelveData")
    return j

@app.get("/api/finnhub/quote")
async def finnhub_quote(symbol: str = Query(...)):
    """
    Proxy to Finnhub quote. Example:
    /api/finnhub/quote?symbol=AAPL
    """
    if not FINNHUB_KEY:
        raise HTTPException(status_code=500, detail="Server missing FINNHUB_KEY")
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": symbol, "token": FINNHUB_KEY}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
    try:
        j = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Bad response from Finnhub")
    return j
