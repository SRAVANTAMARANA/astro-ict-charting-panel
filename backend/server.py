from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect, Header, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os, json, datetime, httpx, asyncio
from functools import wraps

app = FastAPI(title="ICT Charting Backend with WS")

BASE_DIR = os.path.dirname(__file__)
SIGNALS_FILE = os.path.join(BASE_DIR, 'signals.json')
TWELVE_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
API_TOKEN = os.getenv("API_TOKEN", "changeme")

# ensure signals file
if not os.path.exists(SIGNALS_FILE):
    with open(SIGNALS_FILE, 'w') as f:
        json.dump({}, f)

def read_signals():
    try:
        with open(SIGNALS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def write_signals(d):
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(d, f, indent=2)

# auth dependency
def require_token(token: Optional[str] = None, authorization: Optional[str] = Header(None)):
    # try header Bearer
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer' and parts[1] == API_TOKEN:
            return True
    # try query token
    if token and token == API_TOKEN:
        return True
    raise HTTPException(status_code=401, detail="Unauthorized: missing or invalid token")

@app.get("/ict/health")
async def health():
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat() + "Z"}

@app.get("/ict/candles")
async def get_candles(symbol: str = Query(...), interval: str = "1min", limit: int = 200):
    # TwelveData fallback
    if TWELVE_KEY:
        url = "https://api.twelvedata.com/time_series"
        params = {"symbol": symbol, "interval": interval, "outputsize": limit, "format": "JSON", "apikey": TWELVE_KEY}
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params=params)
            data = r.json()
            if "values" in data:
                vals = list(reversed(data["values"]))
                candles = []
                for v in vals:
                    dt = v.get("datetime") or v.get("timestamp")
                    candles.append({
                        "time": dt,
                        "open": float(v["open"]),
                        "high": float(v["high"]),
                        "low": float(v["low"]),
                        "close": float(v["close"]),
                        "volume": float(v.get("volume", 0))
                    })
                return {"symbol": symbol, "candles": candles}
            return JSONResponse({"symbol": symbol, "candles": [], "error": data}, status_code=502)

    # fallback synthetic candles
    now = datetime.datetime.utcnow()
    price = 1900.0
    step = 0.3
    candles = []
    for i in range(limit):
        ts = (now - datetime.timedelta(minutes=(limit - i))).isoformat() + "Z"
        o = price
        h = price + step * 2
        l = price - step * 2
        c = price + (step if i % 2 == 0 else -step)
        v = 100 + i
        candles.append({"time": ts, "open": round(o,5), "high": round(h,5), "low": round(l,5), "close": round(c,5), "volume": v})
        price = c
    return {"symbol": symbol, "candles": candles}

class SignalIn(BaseModel):
    time: Optional[str]
    type: str
    price: float
    note: Optional[str] = ""

@app.get("/ict/signals")
async def get_signals(symbol: str = Query(...)):
    all_signals = read_signals()
    return {"symbol": symbol, "signals": all_signals.get(symbol, [])}

# Broadcast websocket manager
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict):
        living = []
        for ws in list(self.active):
            try:
                await ws.send_json(message)
                living.append(ws)
            except:
                pass
        self.active = living

manager = ConnectionManager()

@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive: clients can send pings
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/ict/signals/add")
async def add_signal(symbol: str = Query(...), s: SignalIn = None, token: str = Query(None), auth: bool = Depends(lambda token=None, authorization=None: require_token(token, authorization))):
    if s is None:
        raise HTTPException(status_code=400, detail="Missing signal body")
    all_signals = read_signals()
    arr = all_signals.get(symbol, [])
    sig = {"time": s.time or datetime.datetime.utcnow().isoformat() + "Z", "type": s.type, "price": s.price, "note": s.note}
    arr.append(sig)
    all_signals[symbol] = arr
    write_signals(all_signals)
    # broadcast to websockets
    asyncio.create_task(manager.broadcast({"type":"signal","symbol":symbol,"signal":sig}))
    return {"ok": True, "signal": sig}
