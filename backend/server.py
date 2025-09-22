from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI(title="ICT Charting Panel API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Replace these with your real keys before running ===
TWELVEDATA_KEY = "PASTE_TWELVEDATA_KEY"
ALPHAV_KEY = "PASTE_ALPHAVANTAGE_KEY"
FINNHUB_KEY = "PASTE_FINNHUB_KEY"
# =======================================================

def fetch_from_twelvedata(symbol: str, interval: str, limit: int):
    url = "https://api.twelvedata.com/time_series"
    params = {"symbol": symbol, "interval": interval, "outputsize": limit, "apikey": TWELVEDATA_KEY}
    r = requests.get(url, params=params, timeout=12)
    r.raise_for_status()
    return r.json()

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ICT Charting Panel API"}

@app.get("/ict/candles")
async def candles(symbol: str = "XAU/USD", interval: str = "1min", limit: int = 50):
    try:
        data = fetch_from_twelvedata(symbol.replace("/", ""), interval=interval, limit=limit)
        vals = data.get("values", [])
        out = []
        for v in vals:
            out.append({
                "t": v.get("datetime"),
                "open": float(v.get("open", 0)),
                "high": float(v.get("high", 0)),
                "low": float(v.get("low", 0)),
                "close": float(v.get("close", 0)),
                "volume": float(v.get("volume", 0)),
            })
        return {"symbol": symbol, "candles": out}
    except Exception as e:
        return {"error": str(e)}

@app.get("/ict/signals")
async def signals():
    return {"signals":[{"id":"s1","type":"BUY","price":3747.2,"desc":"Demo buy"},{"id":"s2","type":"SELL","price":3725.0,"desc":"Demo sell"}]}

@app.get("/ict/ai-mentor")
async def ai_mentor():
    return {"narrative":"AI Mentor sample: watch FVG & liquidity zones. This is demo text."}
