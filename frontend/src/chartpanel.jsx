import React, { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";

export default function ChartPanel({ symbol, interval }) {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);
  const seriesRef = useRef(null);
  const [candles, setCandles] = useState([]);
  const [signals, setSignals] = useState([]);
  const wsRef = useRef(null);
  const [drawMode, setDrawMode] = useState(null); // 'rect' | 'hline' | null
  const drawingsRef = useRef([]); // stores drawing objects in pixel coords then converted to time/price on save

  // initialize chart
  useEffect(() => {
    const el = chartRef.current;
    chartInstance.current = createChart(el, { width: el.clientWidth, height: 480, layout: { backgroundColor: '#071526', textColor: '#dfeffb' } });
    seriesRef.current = chartInstance.current.addCandlestickSeries({ upColor: "#1b8f4f", downColor: "#d9534f", wickUpColor: "#1b8f4f", wickDownColor: "#d9534f" });
    window.addEventListener("resize", () => chartInstance.current.applyOptions({ width: el.clientWidth }));
    return () => chartInstance.current.remove();
  }, []);

  // fetch candles for rendering and mapping
  useEffect(() => {
    async function load() {
      const resp = await fetch(`/ict/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=500`);
      const j = await resp.json();
      const arr = j.candles.map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      }));
      setCandles(arr);
      seriesRef.current.setData(arr);
    }
    load();
  }, [symbol, interval]);

  // fetch and render signals periodically
  useEffect(() => {
    async function loadSignals() {
      const r = await fetch(`/signals`);
      const j = await r.json();
      const s = j.signals || [];
      setSignals(s);
      renderMarkers(s);
    }
    loadSignals();
    const id = setInterval(loadSignals, 3000);
    return () => clearInterval(id);
  }, []);

  // websocket for realtime updates
  useEffect(() => {
    wsRef.current = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
    wsRef.current.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "signals_update") {
          setSignals(m.signals || []);
          renderMarkers(m.signals || []);
        }
      } catch (e) { }
    };
    return () => wsRef.current && wsRef.current.close();
  }, []);

  // marker renderer
  function renderMarkers(signalList) {
    try {
      const markers = (signalList || []).map(s => {
        let time = s.time;
        return {
          time: time,
          position: (s.type && (s.type.includes("BUY") || s.type.includes("LONG") || s.type.includes("BUY"))) ? "belowBar" : "aboveBar",
          color: (s.type && (s.type.includes("BUY") || s.type.includes("LONG"))) ? "#24b47e" : "#ff6b6b",
          shape: (s.type && (s.type.includes("BUY") || s.type.includes("LONG"))) ? "arrowUp" : "arrowDown",
          text: s.type
        };
      });
      seriesRef.current.setMarkers(markers);
    } catch (e) {
      console.warn("marker error", e);
    }
  }

  // drawing: we capture pointer coordinates relative to chart div and store as pixels.
  useEffect(() => {
    const el = chartRef.current;
    if (!el) return;
    function onPointerDown(e) {
      if (!drawMode) return;
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const active = { id: `d_${Date.now()}`, mode: drawMode, x1: x, y1: y, x2: x, y2: y };
      drawingsRef.current.push(active);
      const onMove = (ev) => {
        active.x2 = ev.clientX - rect.left;
        active.y2 = ev.clientY - rect.top;
        renderDrawings();
      };
      const onUp = (ev) => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        renderDrawings();
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    }
    el.addEventListener("pointerdown", onPointerDown);
    return () => el.removeEventListener("pointerdown", onPointerDown);
  }, [drawMode]);

  // render drawing overlays to a canvas overlay element inside chart div
  function renderDrawings() {
    const el = chartRef.current;
    if (!el) return;
    let overlay = el.querySelector("canvas.draw-overlay");
    if (!overlay) {
      overlay = document.createElement("canvas");
      overlay.className = "draw-overlay";
      overlay.style.position = "absolute";
      overlay.style.left = "0";
      overlay.style.top = "0";
      overlay.style.pointerEvents = "none";
      el.appendChild(overlay);
    }
    overlay.width = el.clientWidth;
    overlay.height = el.clientHeight;
    const ctx = overlay.getContext("2d");
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    drawingsRef.current.forEach(d => {
      ctx.strokeStyle = d.mode === "rect" ? "rgba(30,180,255,0.9)" : "rgba(255,180,0,0.95)";
      ctx.lineWidth = 2;
      if (d.mode === "rect") {
        ctx.strokeRect(Math.min(d.x1, d.x2), Math.min(d.y1, d.y2), Math.abs(d.x2 - d.x1), Math.abs(d.y2 - d.y1));
      } else if (d.mode === "hline") {
        const y = d.y1;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(overlay.width, y); ctx.stroke();
      }
    });
  }

  // convert pixel coords to time & price using candle array and visible price range
  // This method uses the loaded `candles` array to compute mapping proportionally
  function pixelToTimePrice(px, py) {
    const el = chartRef.current;
    const w = el.clientWidth;
    const h = el.clientHeight;
    if (!candles || candles.length === 0) return null;
    // time mapping by index proportion
    const idx = Math.round((px / w) * (candles.length - 1));
    const time = candles[Math.max(0, Math.min(candles.length - 1, idx))].time;
    // price mapping: compute visible min/max from loaded candles
    let visible = candles; // for simplicity use all candles; for production use visible window
    let pmin = Math.min(...visible.map(c => c.low));
    let pmax = Math.max(...visible.map(c => c.high));
    // invert y to price
    const price = pmax - ((py / h) * (pmax - pmin));
    return { time, price };
  }

  // convert current drawings (pixel) to saved drawings (time/price) and POST to backend
  async function saveDrawings() {
    const saved = drawingsRef.current.map(d => {
      if (d.mode === "rect") {
        const p1 = pixelToTimePrice(d.x1, d.y1);
        const p2 = pixelToTimePrice(d.x2, d.y2);
        return { id: d.id, type: "rect", time1: p1.time, price1: p1.price, time2: p2.time, price2: p2.price };
      } else if (d.mode === "hline") {
        const p = pixelToTimePrice(d.x1, d.y1);
        return { id: d.id, type: "hline", time: p.time, price: p.price };
      }
      return null;
    }).filter(Boolean);
    // POST to backend (requires token if backend enforces)
    const token = ""; // if you use API_TOKEN, pass Bearer token in header; for now skip
    await fetch("/drawings", {
      method: "POST",
      headers: { "Content-Type": "application/json", /*"Authorization": `Bearer ${token}`*/ },
      body: JSON.stringify({ drawings: saved })
    });
    alert("Drawings saved.");
  }

  // load saved drawings from backend (time/price) and convert to pixel for overlay
  async function loadDrawings() {
    const r = await fetch("/drawings");
    const j = await r.json();
    const saved = j.drawings || [];
    // convert time/price to pixel using our candle array mapping
    const el = chartRef.current;
    const w = el.clientWidth, h = el.clientHeight;
    drawingsRef.current = saved.map(s => {
      if (s.type === "rect") {
        // find nearest indices for times
        const idx1 = nearestIndexForTime(s.time1);
        const idx2 = nearestIndexForTime(s.time2);
        const px1 = (idx1 / (candles.length - 1)) * w;
        const px2 = (idx2 / (candles.length - 1)) * w;
        const visible = candles;
        let pmin = Math.min(...visible.map(c => c.low));
        let pmax = Math.max(...visible.map(c => c.high));
        const py1 = (pmax - s.price1) / (pmax - pmin) * h;
        const py2 = (pmax - s.price2) / (pmax - pmin) * h;
        return { id: s.id, mode: "rect", x1: px1, y1: py1, x2: px2, y2: py2 };
      } else if (s.type === "hline") {
        const idx = nearestIndexForTime(s.time);
        const px = (idx / (candles.length - 1)) * w;
        const visible = candles;
        let pmin = Math.min(...visible.map(c => c.low));
        let pmax = Math.max(...visible.map(c => c.high));
        const py = (pmax - s.price) / (pmax - pmin) * h;
        return { id: s.id, mode: "hline", x1: px, y1: py, x2: px, y2: py };
      }
      return null;
    }).filter(Boolean);
    renderDrawings();
  }

  // helper: nearest candle index for ISO time or unix
  function nearestIndexForTime(t) {
    if (!candles || candles.length === 0) return 0;
    // normalize times: candles.time may be ISO string or unix seconds; compare by string or by parse
    try {
      const target = typeof t === "number" ? t : Date.parse(t) / 1000;
      // build numeric time array (seconds)
      const times = candles.map(c => (typeof c.time === "number" ? c.time : Math.floor(Date.parse(c.time) / 1000)));
      // find nearest index
      let nearest = 0; let bestDiff = Infinity;
      times.forEach((tt, idx) => {
        const diff = Math.abs(tt - target);
        if (diff < bestDiff) { bestDiff = diff; nearest = idx; }
      });
      return nearest;
    } catch (e) {
      return 0;
    }
  }

  // UI controls
  function toggleRect() { setDrawMode(drawMode === "rect" ? null : "rect"); }
  function toggleHLine() { setDrawMode(drawMode === "hline" ? null : "hline"); }
  function clear() { drawingsRef.current = []; renderDrawings(); }

  // re-render drawings when candles change
  useEffect(() => { renderDrawings(); }, [candles]);

  return (
    <div className="chart-wrapper" style={{ position: "relative" }}>
      <div className="chart-toolbar">
        <button onClick={toggleRect} className={drawMode === "rect" ? "active" : ""}>Rect</button>
        <button onClick={toggleHLine} className={drawMode === "hline" ? "active" : ""}>HLine</button>
        <button onClick={clear}>Clear</button>
        <button onClick={saveDrawings}>Save</button>
        <button onClick={loadDrawings}>Load</button>
        <button onClick={() => { document.documentElement.requestFullscreen?.(); }}>Fullscreen</button>
        <button onClick={() => fetch(`/run-detect?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}`, { method: "POST" })}>Run Detect</button>
      </div>

      <div ref={chartRef} className="chart-canvas" style={{ position: "relative", width: "100%" }} />

      <div className="signals-overlay" style={{ position: "absolute", right: 12, top: 12, display: "flex", flexDirection: "column", gap: 6 }}>
        {signals.map((s, i) => <div key={i} className="signal-chip">{s.type} @{typeof s.price === "number" ? s.price.toFixed(4) : s.price}</div>)}
      </div>
    </div>
  );
}
