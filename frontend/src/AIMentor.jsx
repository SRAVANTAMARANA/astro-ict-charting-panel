import React, { useEffect, useState } from "react";

export default function AIMentor({ symbol }) {
  const [narrative, setNarrative] = useState("");
  const [signals, setSignals] = useState([]);

  async function refresh() {
    const r = await fetch(`/mentor?symbol=${encodeURIComponent(symbol)}`);
    const j = await r.json();
    setNarrative(j.narrative || "");
    setSignals(j.signals || []);
    // speak narrative
    if ("speechSynthesis" in window) {
      const utter = new SpeechSynthesisUtterance(j.narrative || "No narrative");
      utter.rate = 0.95;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utter);
    }
  }

  useEffect(() => { refresh(); const id = setInterval(refresh, 60000); return () => clearInterval(id); }, [symbol]);

  return (
    <div className="ai-mentor panel">
      <h3>AI Mentor</h3>
      <pre style={{ whiteSpace: "pre-wrap" }}>{narrative}</pre>
      <div>
        <button onClick={refresh}>Refresh Mentor</button>
      </div>
      <div>
        <h4>Top Signals</h4>
        <ul>
          {signals.map((s, i) => <li key={i}><b>{s.type}</b> {s.desc} {s.price ? `@${s.price}` : ""}</li>)}
        </ul>
      </div>
    </div>
  );
}
