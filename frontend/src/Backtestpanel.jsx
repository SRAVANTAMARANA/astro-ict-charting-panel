import React, { useState } from "react";

export default function BacktestPanel() {
  const [symbol, setSymbol] = useState("XAUUSD");
  const [interval, setInterval] = useState("1min");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  async function runBacktest() {
    setRunning(true);
    const r = await fetch(`/backtest?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&history=800`, { method: "POST" });
    const j = await r.json();
    setResult(j);
    setRunning(false);
  }

  return (
    <div className="backtest panel">
      <h3>Backtest</h3>
      <div>
        <input value={symbol} onChange={e => setSymbol(e.target.value)} />
        <select value={interval} onChange={e => setInterval(e.target.value)}>
          <option>1min</option><option>5min</option><option>15min</option><option>1h</option>
        </select>
        <button onClick={runBacktest} disabled={running}>{running ? "Running..." : "Run Backtest"}</button>
      </div>
      {result && (
        <div>
          <h4>Stats</h4>
          <pre>{JSON.stringify(result.stats, null, 2)}</pre>
          <h4>Samples</h4>
          <pre style={{ maxHeight: 240, overflow: "auto" }}>{JSON.stringify(result.samples.slice(0, 50), null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
