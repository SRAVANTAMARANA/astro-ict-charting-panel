import React, { useState } from "react";
import ChartPanel from "./ChartPanel";
import AIMentor from "./AIMentor";
import BacktestPanel from "./BacktestPanel";
import SignalsTray from "./SignalsTray";

export default function App() {
  const [symbol, setSymbol] = useState("XAUUSD");
  const [interval, setInterval] = useState("1min");
  return (
    <div className="app-root">
      <header className="app-header">
        <h1>Astro ICT Chart Panel</h1>
        <div className="controls">
          <input value={symbol} onChange={e => setSymbol(e.target.value)} />
          <select value={interval} onChange={e => setInterval(e.target.value)}>
            <option value="1min">1m</option><option value="5min">5m</option><option value="15min">15m</option><option value="30min">30m</option>
            <option value="1h">1h</option><option value="1d">1d</option>
          </select>
        </div>
      </header>

      <main className="main-content">
        <div style={{ flex: 1 }}>
          <ChartPanel symbol={symbol} interval={interval} />
        </div>
        <aside style={{ width: 360 }}>
          <AIMentor symbol={symbol} />
          <SignalsTray />
          <BacktestPanel />
        </aside>
      </main>
    </div>
  );
}
