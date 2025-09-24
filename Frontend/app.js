// frontend/app.js
const el = id => document.getElementById(id);
const out = el('out');

async function fetchTimeSeries() {
  const symbol = el('symbol').value.trim() || 'AAPL';
  const interval = el('interval').value || '1min';
  out.textContent = `Fetching time series for ${symbol} (${interval})...\n`;
  try {
    const res = await fetch(`/api/time_series?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}`);
    const j = await res.json();
    out.textContent = JSON.stringify(j, null, 2);
  } catch (err) {
    out.textContent = 'Error: ' + err.toString();
  }
}

async function fetchFinnhub() {
  const symbol = el('symbol').value.trim() || 'AAPL';
  out.textContent = `Fetching Finnhub quote for ${symbol}...\n`;
  try {
    const res = await fetch(`/api/finnhub/quote?symbol=${encodeURIComponent(symbol)}`);
    const j = await res.json();
    out.textContent = JSON.stringify(j, null, 2);
  } catch (err) {
    out.textContent = 'Error: ' + err.toString();
  }
}

el('fetchBtn').addEventListener('click', fetchTimeSeries);
el('finnBtn').addEventListener('click', fetchFinnhub);
