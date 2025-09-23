import React, { useEffect, useState } from "react";

export default function SignalsTray(){
  const [open, setOpen] = useState(true);
  const [signals, setSignals] = useState([]);

  useEffect(()=> {
    async function load(){
      const r = await fetch("/signals");
      const j = await r.json();
      setSignals(j.signals || []);
    }
    load();
    const id = setInterval(load, 3000);
    return ()=> clearInterval(id);
  },[]);

  return (
    <div className={"signals-tray " + (open ? "open":"closed")}>
      <button className="tray-toggle" onClick={()=>setOpen(!open)}>{open ? "Hide":"Show"}</button>
      <div className="tray-content">
        <h3>Signals</h3>
        <ul>
          {signals.map((s,i)=> (
            <li key={i}>
              <b>{s.type}</b> {s.desc || ""} {s.price ? `@${s.price}` : ""}
              <div className="sig-meta">{s.time}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
