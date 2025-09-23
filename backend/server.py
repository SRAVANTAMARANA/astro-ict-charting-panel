# backend/server.py
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

# detectors
from detectors.fvg import detect_fvg
from detectors.liquidity import detect_liquidity
from detectors.turtle_soup import detect_turtle_soup
from detectors.market_structure import detect_market_structure
from detectors.signal_ranker import rank_signals

TWELVE_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
API_TOKEN = os.getenv("API_TOKEN", "").strip()
PORT = int(os.getenv("PORT", "8000"))

BASE_DIR = os.path.dirname(__file__)
SIGNALS_FILE = os.path.join(BASE_DIR, "signals.json")
DRAWINGS_FILE = os.path.join(BASE_DIR, "drawings.json")
BACKTESTS_FILE = os.path.join(BASE_DIR, "backtests.json")

app = FastAPI(title="ICT Charting Backend — Full")

# ensure files exist
for p, init in [(SIGNALS_FILE, []), (DRAWINGS_FILE, []), (BACKTESTS_FILE, {})]:
    if not os.path.exists(p):
        with open(p, "w") as f:
            json.dump(init, f, indent=2)

# helpers
def read_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return None

def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def require_token(authorization: Optional[str] = Header(None)):
    if API_TOKEN:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing token")
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != API_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid token")
    return True

class Candle(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0.0

# --- fetchers (TwelveData -> Finnhub -> synthetic) ---
async def fetch_twelvedata(symbol: str, interval: str, limit: int):
    if not TWELVE_KEY:
        raise RuntimeError("No TwelveData key")
    url = "https://api.twelvedata.com/time_series"
    params = {"symbol": symbol, "interval": interval, "outputsize": limit, "format": "JSON", "apikey": TWELVE_KEY}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        j = r.json()
        if "values" not in j:
            raise RuntimeError(f"TwelveData returned: {j}")
        vals = list(reversed(j["values"]))
        candles = []
        for v in vals[:limit]:
            ts = v.get("datetime") or v.get("timestamp")
            candles.append(Candle(
                time=ts,
                open=float(v["open"]),
                high=float(v["high"]),
                low=float(v["low"]),
                close=float(v["close"]),
                volume=float(v.get("volume", 0.0))
            ))
        return candles

async def fetch_finnhub(symbol: str, interval: str, limit: int):
    if not FINNHUB_KEY:
        raise RuntimeError("No Finnhub key")
    # simple resolution map for common intervals
    res_map = {"1min":"1","5min":"5","15min":"15","30min":"30","1h":"60","1d":"D"}
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
        candles = []
        for i, t in enumerate(j["t"][:limit]):
            candles.append(Candle(
                time=datetime.datetime.utcfromtimestamp(t).isoformat() + "Z",
                open=float(j["o"][i]),
                high=float(j["h"][i]),
                low=float(j["l"][i]),
                close=float(j["c"][i]),
                volume=float(j["v"][i]) if "v" in j else 0.0
            ))
        return candles

def synthetic_candles(symbol: str, interval: str, limit: int):
    now = datetime.datetime.utcnow()
    candles = []
    price = 100.0
    step = 0.1
    for i in range(limit):
        t = now - datetime.timedelta(minutes=(limit - i) * (1 if interval == "1min" else 5))
        o = price + (i % 5 - 2) * step
        c = o + (-1) ** i * step
        h = max(o, c) + step / 2
        l = min(o, c) - step / 2
        candles.append(Candle(time=t.isoformat() + "Z", open=round(o, 6), high=round(h, 6),
                              low=round(l, 6), close=round(c, 6), volume=100 + i))
        price = c
    return candles

# --- detectors wiring (imports at top) ---
def run_detectors(symbol: str, candles: List[Candle]) -> List[Dict[str, Any]]:
    data = [c.dict() for c in candles]
    signals = []
    signals += detect_liquidity(data)
    signals += detect_turtle_soup(data)
    signals += detect_fvg(data)
    signals += detect_market_structure(data)
    for s in signals:
        s.setdefault("symbol", symbol)
        s.setdefault("time", data[-1]["time"] if data else datetime.datetime.utcnow().isoformat() + "Z")
    signals = rank_signals(signals)
    write_json(SIGNALS_FILE, signals)
    return signals

# --- websocket manager ---
class ConnectionManager:
    def __init__(self):
        self.active = []
    async def connect(self, ws):
        await ws.accept()
        self.active.append(ws)
    def disconnect(self, ws):
        if ws in self.active:
            self.active.remove(ws)
    async def broadcast(self, message: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except:
                try:
                    self.disconnect(ws)
                except:
                    pass

manager = ConnectionManager()

# ---------- endpoints ----------
@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat() + "Z"}

@app.get("/ict/candles")
async def get_candles(symbol: str = Query("XAUUSD"), interval: str = Query("1min"), limit: int = Query(200)):
    # try TwelveData -> Finnhub -> synthetic
    if TWELVE_KEY:
        try:
            data = await fetch_twelvedata(symbol, interval, limit)
            return {"symbol": symbol, "candles": [c.dict() for c in data]}
        except Exception:
            pass
    if FINNHUB_KEY:
        try:
            data = await fetch_finnhub(symbol, interval, limit)
            return {"symbol": symbol, "candles": [c.dict() for c in data]}
        except Exception:
            pass
    data = synthetic_candles(symbol, interval, limit)
    return {"symbol": symbol, "candles": [c.dict() for c in data], "note": "synthetic fallback"}

@app.get("/signals")
async def get_signals():
    return {"signals": read_json(SIGNALS_FILE) or []}

@app.post("/run-detect")
async def run_detect(symbol: str = Query("XAUUSD"), interval: str = Query("1min"), limit: int = Query(200)):
    res = await get_candles(symbol, interval, limit)
    candles = [Candle(**c) for c in res["candles"]]
    signals = run_detectors(symbol, candles)
    # broadcast
    asyncio.create_task(manager.broadcast({"type": "signals_update", "signals": signals}))
    return {"status": "ok", "signals": signals}

# drawings endpoints (frontend saves drawings as time/price coordinates)
@app.get("/drawings")
async def get_drawings():
    return {"drawings": read_json(DRAWINGS_FILE) or []}

@app.post("/drawings")
async def post_drawings(payload: dict, authorization: Optional[str] = Header(None)):
    require_token(authorization)
    drawings = payload.get("drawings", [])
    write_json(DRAWINGS_FILE, drawings)
    return {"ok": True}

# mentor endpoint: generate textual narrative from last signals + market structure
@app.get("/mentor")
async def get_mentor(symbol: str = Query("XAUUSD")):
    # load latest candles & signals
    res = await get_candles(symbol, "1min", 200)
    candles = res["candles"]
    signals = read_json(SIGNALS_FILE) or []
    # prioritise top signals
    top = signals[:5] if signals else []
    # compute simple sentiment & market structure
    ms = [s for s in signals if s.get("type", "").startswith("MS_")]
    structure = ms[0]["type"] if ms else "MS_NO_CLEAR"
    # build narrative
    lines = []
    lines.append(f"Market: {symbol}. Time (UTC): {datetime.datetime.utcnow().isoformat()}")
    lines.append(f"Market structure: {structure.replace('MS_','')}")
    if top:
        lines.append("Top signals:")
        for s in top:
            typ = s.get("type")
            pr = s.get("price")
            desc = s.get("desc","")
            lines.append(f"- {typ} at {pr} ({desc})")
    else:
        lines.append("No high-priority signals right now.")
    # trade guidance (very basic)
    guidance = "Be cautious. Use tight risk and confirm with higher timeframes."
    if any(s.get("type","").endswith("BUY") or "LONG" in s.get("type","") for s in top):
        guidance = "Bias: BUY. Consider long entries on pullbacks to nearby support or FVG with stop below recent low."
    if any(s.get("type","").endswith("SELL") or "SHORT" in s.get("type","") for s in top):
        guidance = "Bias: SELL. Consider short entries on pullbacks to resistance or FVG with stop above recent high."
    lines.append("Guidance: " + guidance)
    narrative = "\n".join(lines)
    return {"narrative": narrative, "signals": top, "structure": structure}

# backtest endpoint: run detectors across historical candles sliding-window and compute simple stats
@app.post("/backtest")
async def run_backtest(symbol: str = Query("XAUUSD"), interval: str = Query("1min"), history: int = Query(1000)):
    # fetch extended series
    res = await get_candles(symbol, interval, limit=history)
    candles = [c for c in res["candles"]]
    n = len(candles)
    results = []
    wins = 0; losses = 0; neutral = 0
    # naive backtest: when a BUY-type signal occurs, next N bars result measured at fixed horizon
    horizon = 5  # bars ahead to measure
    for i in range(30, n - horizon):
        window = [Candle(**c) for c in candles[:i+1]]
        # run detectors only on window
        sigs = run_detectors(symbol, window)
        if not sigs:
            continue
        top = sigs[0]
        typ = top.get("type","")
        entry_price = float(top.get("price") or window[-1].close)
        future_close = float(candles[i+horizon]["close"])
        pnl = future_close - entry_price
        if typ.upper().endswith("BUY") or "LONG" in typ:
            outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "neutral")
        elif typ.upper().endswith("SELL") or "SHORT" in typ:
            outcome = "win" if pnl < 0 else ("loss" if pnl > 0 else "neutral")
        else:
            outcome = "neutral"
        if outcome == "win": wins += 1
        elif outcome == "loss": losses += 1
        else: neutral += 1
        results.append({"index": i, "type": typ, "entry": entry_price, "future_close": future_close, "pnl": pnl, "outcome": outcome})
    total = max(1, wins + losses + neutral)
    stats = {"total_signals_tested": total, "wins": wins, "losses": losses, "neutral": neutral,
             "win_rate": round(wins / total * 100, 2)}
    # store backtest snapshot
    backtests = read_json(BACKTESTS_FILE) or {}
    stamp = datetime.datetime.utcnow().isoformat() + "Z"
    backtests[stamp] = {"symbol": symbol, "interval": interval, "horizon": horizon, "stats": stats}
    write_json(BACKTESTS_FILE, backtests)
    return {"stats": stats, "samples": results[:200]}

# WebSocket endpoint (simple)
from fastapi import WebSocket, WebSocketDisconnect
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            # echo (keeps connection alive)
            await ws.send_json({"echo": data})
    except WebSocketDisconnect:
        manager.disconnect(ws)

# trigger for test
@app.post("/trigger/tick")
async def trigger_tick(authorization: Optional[str] = Header(None)):
    require_token(authorization)
    tick = {"time": int(datetime.datetime.utcnow().timestamp()), "price": 100 + (datetime.datetime.utcnow().second % 10) * 0.1}
    asyncio.create_task(manager.broadcast({"type": "tick", "tick": tick}))
    return {"tick": tick}

# if run as script
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=False)
