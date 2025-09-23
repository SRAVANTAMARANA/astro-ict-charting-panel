# backend/server.py
"""
ICT Charting Panel - Backend (FastAPI)
Provides:
 - /ict/candles  -> fetches market candles (TwelveData primary, Finnhub fallback)
 - /ict/signals  -> GET/POST stored signals (persisted in signals.json)
 - /ict/detect   -> run quick detector using simple SMA crossover + histogram rule
 - /ws/signals    -> websocket broadcast for realtime signals
 - /ict/health, /ict/config, /ict/maxmin
 - simple scheduler to run detector periodically (optional)
"""
import os
import json
import asyncio
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx

# try to load .env if exists (python-dotenv optional)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except Exception:
    pass

# CONFIG (from env)
TWELVEDATA_KEY = os.getenv("TWELVEDATA_KEY", "").strip()
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "").strip()
SIGNALS_FILE = Path(__file__).resolve().parent / "signals.json"
CANDLES_CACHE_DIR = Path(__file__).resolve().parent / "cache"
CANDLES_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# create signals file if missing
if not SIGNALS_FILE.exists():
    SIGNALS_FILE.write_text(json.dumps({"signals": []}, indent=2))

app = FastAPI(title="Astro ICT Charting Backend")

# ---------------------------
# Pydantic models
# ---------------------------
class Candle(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

class Signal(BaseModel):
    id: Optional[str]
    symbol: str
    time: str
    type: str  # e.g., "BUY", "SELL", "INFO"
    price: float
    detail: Optional[str] = ""
    icon: Optional[str] = ""  # e.g., "ict-buy", "ict-sell"
    meta: Optional[Dict[str, Any]] = {}

# ---------------------------
# Persistence helpers
# ---------------------------
def read_signals() -> List[Dict]:
    try:
        with SIGNALS_FILE.open("r") as f:
            data = json.load(f)
            return data.get("signals", [])
    except Exception:
        return []

def write_signals(signals: List[Dict]):
    with SIGNALS_FILE.open("w") as f:
        json.dump({"signals": signals}, f, indent=2, default=str)

def append_signal(sig: Dict):
    s = read_signals()
    s.append(sig)
    write_signals(s)

# ---------------------------
# Simple WebSocket broadcaster
# ---------------------------
class Broadcaster:
    def __init__(self):
        self._clients: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)

    async def broadcast(self, message: dict):
        # send to each client; swallow errors
        living = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
                living.append(ws)
            except Exception:
                # ignore broken clients
                pass
        self._clients = living

bcast = Broadcaster()

@app.websocket("/ws/signals")
async def ws_signals(ws: WebSocket):
    await bcast.connect(ws)
    try:
        while True:
            # simple ping/pong
            await ws.receive_text()
            await ws.send_text("pong")
    except WebSocketDisconnect:
        bcast.disconnect(ws)
    except Exception:
        bcast.disconnect(ws)

# ---------------------------
# Market data fetchers
# ---------------------------
async def fetch_twelvedata(symbol: str, interval: str, limit: int = 200) -> Optional[List[dict]]:
    if not TWELVEDATA_KEY:
        return None
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": limit,
        "format": "JSON",
        "apikey": TWELVEDATA_KEY
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            return None
        data = r.json()
    if "values" not in data:
        return None
    vals = list(reversed(data["values"]))
    candles = []
    for v in vals:
        t = v.get("datetime") or v.get("timestamp")
        candles.append({
            "time": t,
            "open": float(v.get("open", 0)),
            "high": float(v.get("high", 0)),
            "low": float(v.get("low", 0)),
            "close": float(v.get("close", 0)),
            "volume": float(v.get("volume", 0) or 0)
        })
    return candles

async def fetch_finnhub(symbol: str, interval: str, limit: int = 200) -> Optional[List[dict]]:
    if not FINNHUB_KEY:
        return None
    mapping = {"1min":"1","5min":"5","15min":"15","30min":"30","1h":"60","60min":"60","1day":"D"}
    res = mapping.get(interval, "1")
    now = int(datetime.datetime.datetime.utcnow().timestamp()) if hasattr(datetime, "datetime") else int(datetime.datetime.now().timestamp())
    # fallback simple window
    seconds_map = {"1": 60, "5": 300, "15": 900, "30": 1800, "60": 3600, "D": 86400}
    sec = seconds_map.get(res, 60)
    start = now - sec * limit
    url = "https://finnhub.io/api/v1/forex/candle"
    params = {"symbol": symbol, "resolution": res, "from": start, "to": now, "token": FINNHUB_KEY}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            return None
        data = r.json()
    if data.get("s") != "ok" or "t" not in data:
        return None
    candles = []
    for i, ts in enumerate(data["t"]):
        candles.append({
            "time": datetime.datetime.utcfromtimestamp(ts).isoformat() + "Z",
            "open": float(data["o"][i]),
            "high": float(data["h"][i]),
            "low": float(data["l"][i]),
            "close": float(data["c"][i]),
            "volume": float(data["v"][i]) if "v" in data else 0
        })
    return candles

# cache helper (optional)
def _cache_path(symbol: str, interval: str):
    safe = f"{symbol.replace('/', '_')}_{interval}.json"
    return CANDLES_CACHE_DIR / safe

# ---------------------------
# Endpoints
# ---------------------------
@app.get("/ict/health")
async def health():
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat() + "Z"}

@app.get("/ict/config")
async def config():
    return {"twelvedata": bool(TWELVEDATA_KEY), "finnhub": bool(FINNHUB_KEY)}

@app.get("/ict/candles")
async def get_candles(symbol: str = Query(...), interval: str = Query("1min"), limit: int = Query(200, ge=1, le=1000)):
    """
    Main candle endpoint for frontend.
    """
    # try TwelveData
    tw = await fetch_twelvedata(symbol, interval, limit)
    if tw:
        # update cache
        try:
            _cache_path(symbol, interval).write_text(json.dumps({"symbol": symbol, "interval": interval, "candles": tw}))
        except Exception:
            pass
        return {"symbol": symbol, "candles": tw}
    # fallback finnhub
    fh = await fetch_finnhub(symbol, interval, limit)
    if fh:
        try:
            _cache_path(symbol, interval).write_text(json.dumps({"symbol": symbol, "interval": interval, "candles": fh}))
        except Exception:
            pass
        return {"symbol": symbol, "candles": fh}
    # else try cache
    try:
        cp = _cache_path(symbol, interval)
        if cp.exists():
            data = json.loads(cp.read_text())
            return {"symbol": symbol, "candles": data.get("candles", [])}
    except Exception:
        pass
    raise HTTPException(status_code=502, detail="No market data available (keys missing or provider error)")

# signals listing
@app.get("/ict/signals")
async def get_signals(limit: int = 200):
    signals = read_signals()
    return {"count": len(signals), "signals": signals[-limit:]}

# add a signal (called by detector or external)
@app.post("/ict/signals")
async def post_signal(sig: Signal, background: BackgroundTasks):
    obj = sig.dict()
    if not obj.get("id"):
        obj["id"] = f"{int(datetime.datetime.utcnow().timestamp()*1000)}"
    if not obj.get("time"):
        obj["time"] = datetime.datetime.utcnow().isoformat() + "Z"
    append_signal(obj)
    # broadcast asynchronously
    background.add_task(asyncio.create_task, bcast.broadcast({"type": "signal", "payload": obj}))
    return {"ok": True, "signal": obj}

# small utility: compute last max/min/close
@app.get("/ict/maxmin")
async def maxmin(symbol: str = Query(...), interval: str = Query("1min"), lookback: int = Query(50)):
    r = await get_candles(symbol=symbol, interval=interval, limit=lookback)
    candles = r.get("candles", [])
    if not candles:
        raise HTTPException(404, "no candles")
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    return {"symbol": symbol, "highest": max(highs), "lowest": min(lows), "last_close": closes[-1]}

# ---------------------------
# Simple detector implementation
# ---------------------------
def sma(values: List[float], period: int) -> List[Optional[float]]:
    out = []
    for i in range(len(values)):
        if i+1 < period:
            out.append(None)
        else:
            window = values[i+1-period:i+1]
            out.append(sum(window)/period)
    return out

async def run_detector(symbol: str, interval: str = "1min", limit: int = 200) -> Dict:
    """
    Detector runs lightweight signals:
      - SMA short/long crossover
      - simple MACD histogram sign change (approx using EMA-like simple)
    It will append signals into signals.json and broadcast.
    """
    res = await get_candles(symbol=symbol, interval=interval, limit=limit)
    candles = res.get("candles", [])
    if len(candles) < 20:
        return {"ok": False, "reason": "not enough candles", "len": len(candles)}
    closes = [c["close"] for c in candles]
    # compute sma10 and sma21
    s10 = sma(closes, 10)
    s21 = sma(closes, 21)
    # get last two values to detect cross
    idx = len(closes) - 1
    def safe(vlist, i): return vlist[i] if i >= 0 and i < len(vlist) else None
    prev_short = safe(s10, idx-1)
    prev_long = safe(s21, idx-1)
    cur_short = safe(s10, idx)
    cur_long = safe(s21, idx)
    signals_generated = []
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    price = closes[-1]
    # SMA cross detection
    if prev_short and prev_long and cur_short and cur_long:
        if prev_short < prev_long and cur_short >= cur_long:
            sig = {
                "id": f"det-{int(datetime.datetime.utcnow().timestamp()*1000)}",
                "symbol": symbol,
                "time": now_iso,
                "type": "BUY",
                "price": price,
                "detail": f"sma10 crossed above sma21 ({cur_short:.5f} >= {cur_long:.5f})",
                "icon": "ict-buy",
                "meta": {"interval": interval}
            }
            append_signal(sig); signals_generated.append(sig)
            await bcast.broadcast({"type": "signal", "payload": sig})
        elif prev_short > prev_long and cur_short <= cur_long:
            sig = {
                "id": f"det-{int(datetime.datetime.utcnow().timestamp()*1000)}",
                "symbol": symbol,
                "time": now_iso,
                "type": "SELL",
                "price": price,
                "detail": f"sma10 crossed below sma21 ({cur_short:.5f} <= {cur_long:.5f})",
                "icon": "ict-sell",
                "meta": {"interval": interval}
            }
            append_signal(sig); signals_generated.append(sig)
            await bcast.broadcast({"type": "signal", "payload": sig})
    # simple momentum check - price spike: last close vs previous average
    prev_avg = sum(closes[-6:-1]) / 5 if len(closes) >= 6 else None
    if prev_avg:
        if price > prev_avg * 1.01:
            sig = {
                "id": f"moment-{int(datetime.datetime.utcnow().timestamp()*1000)}",
                "symbol": symbol,
                "time": now_iso,
                "type": "INFO",
                "price": price,
                "detail": f"price > prev5_avg * 1.01 ({prev_avg:.5f})",
                "icon": "ict-spike",
                "meta": {"interval": interval}
            }
            append_signal(sig); signals_generated.append(sig)
            await bcast.broadcast({"type": "signal", "payload": sig})
    return {"ok": True, "generated": len(signals_generated), "signals": signals_generated}

@app.post("/ict/detect")
async def endpoint_detect(symbol: str = Query(...), interval: str = Query("1min"), background: BackgroundTasks = None):
    """
    Trigger detector immediately. Returns generated signals.
    """
    result = await run_detector(symbol=symbol, interval=interval, limit=200)
    return result

# ---------------------------
# Simple scheduler (optional): run detector every N seconds for a set of pairs.
# Not started by default; call start_scheduler() manually or run in container startup script.
# ---------------------------
_scheduler_task = None
async def _scheduler_loop(pairs: List[Dict], interval_seconds: int = 30):
    try:
        while True:
            for p in pairs:
                try:
                    await run_detector(symbol=p["symbol"], interval=p.get("interval", "1min"), limit=p.get("limit", 200))
                except Exception:
                    pass
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        return

def start_scheduler(pairs: List[Dict], interval_seconds: int = 30):
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return
    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_scheduler_loop(pairs, interval_seconds))

def stop_scheduler():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None

# Optional endpoint to control scheduler
@app.post("/ict/scheduler/start")
async def api_scheduler_start(pairs: List[Dict] = [{"symbol":"XAUUSD","interval":"1min"}], interval_seconds: int = 60):
    start_scheduler(pairs, interval_seconds)
    return {"ok": True, "started_for": pairs, "interval_seconds": interval_seconds}

@app.post("/ict/scheduler/stop")
async def api_scheduler_stop():
    stop_scheduler()
    return {"ok": True, "stopped": True}

# ---------------------------
# Run helper
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    # recommended test host/port
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)
