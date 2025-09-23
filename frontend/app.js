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
