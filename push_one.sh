#!/usr/bin/env bash
set -e
# ONE-PUSH: writes the complete ICT charting panel (frontend + backend),
# commits locally and optionally pushes to remote (you will paste PAT when prompted).
# Run in repo root. BACKUP first if needed.

REPO_ROOT="$(pwd)"
echo "Working in: $REPO_ROOT"

##########################
# docker-compose
##########################
cat > docker-compose.yml <<'YAML'
version: '3.8'
services:
  backend:
    build: ./backend
    env_file:
      - ./backend/.env
    environment:
      - TWELVEDATA_API_KEY=${TWELVEDATA_API_KEY:-}
      - API_TOKEN=${API_TOKEN:-changeme}
    ports:
      - "8000:8000"
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    restart: unless-stopped
YAML

##########################
# Backend files
##########################
mkdir -p backend
cat > backend/Dockerfile <<'DOCKER'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
DOCKER

cat > backend/requirements.txt <<'REQ'
fastapi
uvicorn[standard]
httpx
python-dotenv
pydantic
REQ

cat > backend/.env <<'ENV'
# Put actual keys here or set in compose environment
TWELVEDATA_API_KEY=
API_TOKEN=changeme
ENV

cat > backend/server.py <<'PY'
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
PY

##########################
# Frontend files
##########################
mkdir -p frontend
cat > frontend/Dockerfile <<'NDOCK'
FROM nginx:stable-alpine
COPY . /usr/share/nginx/html
EXPOSE 80
NDOCK

cat > frontend/ictpanel.html <<'HTML'
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Astro ICT Chart Panel</title>
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <link rel="stylesheet" href="styles.css" />
  <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
  <!-- interact.js for drag & resize -->
  <script src="https://cdn.jsdelivr.net/npm/interactjs/dist/interact.min.js"></script>
</head>
<body>
  <header>
    <h1>Astro ICT Chart Panel</h1>
    <div class="controls">
      <input id="symbol" value="XAUUSD" />
      <select id="interval">
        <option value="1min">1m</option>
        <option value="5min">5m</option>
        <option value="15min">15m</option>
        <option value="1h">1h</option>
      </select>
      <button id="loadBtn">Load</button>
      <button id="tvBtn" title="Open TradingView widget">TV</button>
      <button id="fullscreenBtn">Fullscreen</button>
      <label><input id="themeToggle" type="checkbox"> Dark</label>
    </div>
  </header>

  <main>
    <div id="chartPanel" class="panel" data-resizable>
      <div id="chart" class="chart"></div>
      <div id="chart-stats" class="chart-stats">
        Min: <span id="minVal">-</span> | Max: <span id="maxVal">-</span> | Close: <span id="closeVal">-</span>
      </div>
    </div>

    <aside id="rightPanel" class="panel right" data-resizable>
      <h2>AI Mentor</h2>
      <div id="aiMentor">
        <button id="refreshMentor">Refresh Mentor</button>
        <p id="mentorText">AI mentor demo text</p>
      </div>

      <h2>Signals</h2>
      <div id="signalsTray" class="signals-tray">
        <button id="toggleSignals">Show / Hide</button>
        <div id="signalsList" class="signals-list"></div>
      </div>
    </aside>
  </main>

  <footer>
    <div id="statusBox">Status: <span id="statusText">idle</span></div>
  </footer>

  <!-- TV widget container -->
  <div id="tvWidget" class="tv-widget hidden">
    <div id="tvClose">✖</div>
    <div id="tradingview_container" style="width:100%;height:100%;"></div>
  </div>

  <script src="app.js"></script>
</body>
</html>
HTML

cat > frontend/styles.css <<'CSS'
:root {
  --bg: #f5f7fb;
  --panel: #ffffff;
  --text: #072b3a;
  --accent: #1976d2;
}
:root.dark {
  --bg: #0b1220;
  --panel: #0f1724;
  --text: #dbeafe;
  --accent: #4fc3f7;
}
html,body{height:100%;margin:0;background:var(--bg);color:var(--text);font-family:Arial, sans-serif;}
header{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;background:var(--panel);box-shadow:0 1px 4px rgba(0,0,0,0.06);}
.controls input,.controls select{padding:6px;margin-right:6px;}
main{display:flex;gap:12px;padding:12px;}
.panel{background:var(--panel);border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.08);padding:8px;}
#chartPanel{flex:1;display:flex;flex-direction:column;min-height:520px;position:relative;resize:both;overflow:auto;}
#chart{flex:1;height:520px;}
.chart-stats{padding:6px;border-top:1px solid rgba(0,0,0,0.05);font-size:14px;}
.right{width:320px;min-width:240px;}
.signals-tray{margin-top:8px;}
.signals-list{max-height:360px;overflow:auto;margin-top:8px;}
#statusBox{padding:8px;position:fixed;right:18px;bottom:18px;background:var(--panel);border-radius:6px;box-shadow:0 6px 20px rgba(0,0,0,0.12);}
button{cursor:pointer;padding:6px 8px;margin:3px;border-radius:4px;border:0;background:var(--accent);color:white;}
button.secondary{background:#888;}
.tv-widget { position:fixed; inset:40px 40px 40px 40px; background:#fff; z-index:9999; border-radius:8px; box-shadow:0 10px 40px rgba(0,0,0,0.6); overflow:hidden; }
.tv-widget.hidden{ display:none; }
#tvClose{position:absolute;right:8px;top:6px;z-index:10000;cursor:pointer;padding:6px;color:#fff;background:#333;border-radius:50%;}
CSS

cat > frontend/app.js <<'JS'
/* frontend script with WS, interact.js for drag/resize, lightweight charts and TV toggle */
const backendBase = (location.hostname === 'localhost') ? 'http://localhost:8000' : `${location.origin}/backend`;
const chartDiv = document.getElementById('chart');
let chart = null, candleSeries = null, themeDark = false, ws=null;

function applyTheme(){ document.documentElement.classList.toggle('dark', themeDark); }
document.getElementById('themeToggle').addEventListener('change', (e)=>{ themeDark=e.target.checked; applyTheme(); recreateChart(); });

function recreateChart(){
  if(chart) chart.remove();
  chart = LightweightCharts.createChart(chartDiv, {
    width: chartDiv.clientWidth,
    height: chartDiv.clientHeight,
    layout: { background: { color: themeDark? '#0b1220':'#ffffff' }, textColor: themeDark? '#dbeafe':'#333' },
    rightPriceScale: { borderVisible:false }, timeScale:{ borderVisible:false }
  });
  candleSeries = chart.addCandlestickSeries();
  chart.timeScale().subscribeVisibleTimeRangeChange(updateStats);
}
window.addEventListener('resize', ()=>{ if(chart) chart.applyOptions({width:chartDiv.clientWidth, height:chartDiv.clientHeight}); });
recreateChart();

async function loadCandles(){
  const symbol=document.getElementById('symbol').value||'XAUUSD';
  const interval=document.getElementById('interval').value||'1min';
  setStatus('loading...');
  try{
    const res=await fetch(`${backendBase}/ict/candles?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=400`);
    const payload=await res.json();
    if(!payload||!payload.candles) throw new Error('no candles');
    const data=payload.candles.map(c=>({ time: convertTime(c.time), open:c.open, high:c.high, low:c.low, close:c.close }));
    candleSeries.setData(data);
    setStatus('OK');
    updateStats();
    loadSignals(symbol);
    connectWS(); // ensure websocket connected
  }catch(e){
    console.error(e); setStatus('error '+(e.message||e)); candleSeries.setData([]); updateStats();
  }
}
function convertTime(t){ try{ if(typeof t==='string' && t.includes('T')) return t; return (new Date(t)).toISOString(); }catch{ return t; } }

function setStatus(s){ document.getElementById('statusText').innerText = s; }

function updateStats(){
  if(!chart || !candleSeries) return;
  const vr = chart.timeScale().getVisibleRange();
  if(!vr){ setStats('-','-','-'); return; }
  const symbol=document.getElementById('symbol').value||'XAUUSD';
  fetch(`${backendBase}/ict/candles?symbol=${symbol}&interval=${document.getElementById('interval').value}&limit=1000`)
    .then(r=>r.json()).then(payload=>{
      const arr=(payload.candles||[]).map(x=>({t:convertTime(x.time),low:x.low,high:x.high,close:x.close}));
      const filtered = arr.filter(x=> x.t>=vr.from && x.t<=vr.to);
      if(!filtered.length){ const last=arr.slice(-1)[0]; setStats('-','-',(last? last.close:'-')); return; }
      const lows = filtered.map(x=>x.low), highs=filtered.map(x=>x.high);
      setStats(Math.min(...lows), Math.max(...highs), filtered[filtered.length-1].close);
    }).catch(()=>setStats('-','-','-'));
}
function setStats(min,max,close){ document.getElementById('minVal').innerText=min; document.getElementById('maxVal').innerText=max; document.getElementById('closeVal').innerText=close; }

async function loadSignals(symbol){
  try{
    const res=await fetch(`${backendBase}/ict/signals?symbol=${encodeURIComponent(symbol)}`);
    const json=await res.json();
    const list=document.getElementById('signalsList'); list.innerHTML='';
    (json.signals||[]).forEach(s=>{
      const el=document.createElement('div'); el.textContent=`${s.time} | ${s.type.toUpperCase()} @ ${s.price} ${s.note||''}`;
      list.appendChild(el);
      const marker = chart.addLineSeries({ color: s.type==='buy'?'#2ecc71':'#e74c3c', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed });
      marker.setData([{ time: convertTime(s.time), value: s.price }]);
      setTimeout(()=>marker.remove(), 1000*60*30);
    });
  }catch(e){ console.warn('signals', e); }
}
document.getElementById('toggleSignals').addEventListener('click', ()=> {
  const el=document.getElementById('signalsList'); el.style.display = el.style.display==='none'? 'block' : 'none';
});

// add signal (protected) -> opens prompt for token
async function addSignalPrompt(){
  const symbol = document.getElementById('symbol').value||'XAUUSD';
  const price = prompt("Price for signal:");
  const type = prompt("Type (buy/sell):","buy");
  const token = prompt("API token (protected):");
  if(!price || !type) return;
  try{
    const res = await fetch(`${backendBase}/ict/signals/add?symbol=${encodeURIComponent(symbol)}&token=${encodeURIComponent(token)}`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ time:new Date().toISOString(), type:type, price: parseFloat(price), note:'manual' })
    });
    const json = await res.json();
    console.log('add signal',json);
    loadSignals(symbol);
  }catch(e){ alert('error: '+e.message); }
}

// small UI actions
document.getElementById('refreshMentor').addEventListener('click', ()=> document.getElementById('mentorText').innerText="AI mentor updated "+new Date().toLocaleTimeString());
document.getElementById('loadBtn').addEventListener('click', loadCandles);
document.getElementById('fullscreenBtn').addEventListener('click', ()=> { if(!document.fullscreenElement) document.documentElement.requestFullscreen(); else document.exitFullscreen(); });

// TradingView widget toggle + simple layout save
const tvWidget = document.getElementById('tvWidget');
document.getElementById('tvBtn').addEventListener('click', ()=>{
  if(tvWidget.classList.contains('hidden')){
    const container = document.getElementById('tradingview_container');
    container.innerHTML = '';
    const symbol = document.getElementById('symbol').value || 'XAUUSD';
    const script = document.createElement('script');
    script.src = "https://s3.tradingview.com/tv.js";
    script.onload = ()=> {
      new TradingView.widget({
        "autosize": true,
        "symbol": symbol,
        "interval": "60",
        "timezone": "Etc/UTC",
        "theme": themeDark? "dark" : "light",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_container"
      });
    };
    container.appendChild(script);
    tvWidget.classList.remove('hidden');
    localStorage.setItem('chartMode','tv');
  } else {
    tvWidget.classList.add('hidden');
    document.getElementById('tradingview_container').innerHTML = '';
    localStorage.setItem('chartMode','light');
  }
});
document.getElementById('tvClose').addEventListener('click', ()=> tvWidget.classList.add('hidden'));

// WebSocket real-time signals
function connectWS(){
  if(ws && ws.readyState === WebSocket.OPEN) return;
  try{
    ws = new WebSocket((location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.hostname + ':8000/ws/signals');
    ws.onopen = ()=> console.log('WS open');
    ws.onmessage = (m) => {
      try{
        const data = JSON.parse(m.data);
        if(data.type === 'signal'){
          const symbol=document.getElementById('symbol').value||'XAUUSD';
          if(data.symbol === symbol){
            // show in UI
            const list=document.getElementById('signalsList');
            const el=document.createElement('div'); el.textContent=`(ws) ${data.signal.time} | ${data.signal.type.toUpperCase()} @ ${data.signal.price} ${data.signal.note||''}`;
            list.prepend(el);
            // draw marker
            const marker = chart.addLineSeries({ color: data.signal.type==='buy'?'#2ecc71':'#e74c3c', lineWidth: 1 });
            marker.setData([{ time: convertTime(data.signal.time), value: data.signal.price }]);
            setTimeout(()=>marker.remove(), 1000*60*30);
          }
        }
      }catch(e){ console.warn('ws parse', e); }
    };
    ws.onclose = ()=> { console.log('WS closed, reconnect in 3s'); setTimeout(connectWS,3000); };
    ws.onerror = (e) => { console.warn('WS err', e); ws.close(); };
  }catch(e){ console.warn('ws connect error', e); }
}

loadCandles();
applyTheme();

// interact.js for drag & resize
interact('[data-resizable]').draggable({ inertia:true, modifiers:[interact.modifiers.restrict({restriction:'parent',endOnly:true})], listeners:{
  start (event) {},
  move (event) {
    const target = event.target;
    const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
    const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
    target.style.transform = 'translate(' + x + 'px, ' + y + 'px)';
    target.setAttribute('data-x', x);
    target.setAttribute('data-y', y);
  },
  end (event) {}
}}).resizable({
  edges: { left:true, right:true, bottom:true, top:true },
  listeners: {
    move (event) {
      let { x, y } = event.target.dataset;
      x = (parseFloat(x) || 0);
      y = (parseFloat(y) || 0);
      // update size
      event.target.style.width  = event.rect.width + 'px';
      event.target.style.height = event.rect.height + 'px';
      // translate when resizing from top or left
      x += event.deltaRect.left;
      y += event.deltaRect.top;
      event.target.style.transform = 'translate(' + x + 'px,' + y + 'px)';
      event.target.dataset.x = x;
      event.target.dataset.y = y;
      // if chartPanel resized, update chart
      if(event.target.id === 'chartPanel' && chart) setTimeout(()=>chart.applyOptions({width: chartDiv.clientWidth, height: chartDiv.clientHeight}),50);
    }
  },
  inertia: true
});

// double click to add sample signal (protected) -> prompts for token
chartDiv.addEventListener('dblclick', addSignalPrompt);
JS

##########################
# README
##########################
cat > README.md <<'MD'
# Astro ICT Charting Panel - Full one-push package

This repo contains a FastAPI backend and a static frontend (Lightweight Charts + TradingView widget toggle).  
Services run with Docker Compose.

## Run
1. Build and start:
   docker-compose up --build -d

2. Frontend: http://localhost:3000/  
   Backend: http://localhost:8000/  
   WebSocket: ws://localhost:8000/ws/signals

## Backend protected endpoint
/ict/signals/add is protected by API_TOKEN (set in backend/.env or compose environment).
MD

##########################
# git commit & push
##########################
git add -A
git commit -m "One-push: complete ICT charting panel with websocket, interact.js drag/resize, token-protected signals, TV toggle"

echo "Committed all new files locally."

read -p "Push to remote 'origin' main now? (y/N) " yn
if [[ "$yn" =~ ^[Yy]$ ]]; then
  read -p "Remote repository URL (https://<PAT>@github.com/youruser/yourrepo.git) or press Enter to use current origin: " remote
  if [[ -n "$remote" ]]; then
    git remote remove origin 2>/dev/null || true
    git remote add origin "$remote"
  fi
  echo "Pushing to origin main..."
  git push -u origin main
  echo "Push complete."
else
  echo "Skipping push. You can push later with: git push -u origin main"
fi

echo "One-push finished. Next: set API_TOKEN in backend/.env and run 'docker-compose up --build -d'"
