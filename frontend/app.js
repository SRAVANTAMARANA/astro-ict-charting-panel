// app.js - frontend logic using LightweightCharts standalone build
// Assumes: lightweight-charts standalone script is loaded and exposes `LightweightCharts` global

(function () {
  // DOM elements
  const chartDiv = document.getElementById('chart');
  const symbolInput = document.getElementById('symbol');
  const intervalSelect = document.getElementById('interval');
  const loadBtn = document.getElementById('loadBtn');
  const recreateBtn = document.getElementById('recreateBtn');
  const autoBtn = document.getElementById('autoBtn');
  const logEl = document.getElementById('log');
  const backendHealthEl = document.getElementById('backendHealth');
  const healthStatus = document.getElementById('healthStatus');
  const checkHealthBtn = document.getElementById('checkHealth');
  const testApiBtn = document.getElementById('testApi');

  // Chart variables
  let chart = null;
  let candleSeries = null;
  let autoTimer = null;
  let autoOn = false;

  // Backend config - adjust if your backend serves from different prefix/port
  const BACKEND_BASE = ''; // empty means same origin. If using /api prefix or different port set here (e.g. 'http://localhost:8000')
  // Endpoint paths used by your project
  const CANDLES_ENDPOINT = (s, i) => `${BACKEND_BASE}/ict/candles?symbol=${encodeURIComponent(s)}&interval=${encodeURIComponent(i)}&limit=200`;
  const HEALTH_ENDPOINT = `${BACKEND_BASE}/ict/health`;

  // logging helpers
  function log(...args) {
    console.log(...args);
    const line = args.map(a => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
    logEl.textContent = `${new Date().toISOString()}  ${line}\n` + logEl.textContent;
  }

  function setBackendHealth(statusText, ok = true) {
    backendHealthEl.textContent = statusText;
    backendHealthEl.style.color = ok ? 'green' : 'red';
    healthStatus.textContent = ok ? 'ok' : 'error';
    healthStatus.style.color = ok ? 'green' : 'red';
  }

  // Chart creation using global LightweightCharts (standalone)
  function recreateChart() {
    // destroy previous
    if (chart) {
      try { chart.remove(); } catch (e) { /* ignore */ }
      chart = null;
      candleSeries = null;
    }

    // ensure the global exists
    if (typeof LightweightCharts === 'undefined') {
      log('LightweightCharts global not found. Make sure the standalone script is loaded.');
      return;
    }

    // create chart
    chart = LightweightCharts.createChart(chartDiv, {
      width: chartDiv.clientWidth,
      height: chartDiv.clientHeight,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333'
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false }
    });

    // add candlestick series
    candleSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: true,
      wickVisible: true
    });

    // handle responsive
    window.addEventListener('resize', () => {
      if (!chart) return;
      chart.applyOptions({ width: chartDiv.clientWidth, height: chartDiv.clientHeight });
    });

    log('Chart recreated.');
  }

  // convert backend candle items to LightweightCharts format
  function mapCandlesToLW(dataArray) {
    // expects each item {datetime, open, high, low, close, volume}
    return dataArray.map(item => {
      // Lightweight accepts ISO (yyyy-mm-ddTHH:MM:SSZ) or timestamp in seconds; we pass the ISO directly
      return {
        time: item.datetime || item.time || item.date || item.t, // check multiple field names
        open: Number(item.open),
        high: Number(item.high),
        low: Number(item.low),
        close: Number(item.close),
        volume: item.volume !== undefined ? Number(item.volume) : undefined
      };
    }).filter(Boolean);
  }

  // load candles from backend and populate chart
  async function loadCandles(symbol, interval) {
    if (!symbol) {
      log('Symbol is empty.');
      return;
    }

    try {
      if (!chart || !candleSeries) {
        recreateChart();
      }

      const url = CANDLES_ENDPOINT(symbol, interval);
      log('Fetching candles from', url);
      const res = await fetch(url, { cache: 'no-store' });

      if (!res.ok) {
        const text = await res.text();
        log('Candles request failed', res.status, text);
        setBackendHealth(`candles ${res.status}`, false);
        return;
      }

      const payload = await res.json();
      // payload could either be {meta:..., data: [...]} or just an array
      let array = [];
      if (Array.isArray(payload)) {
        array = payload;
      } else if (payload && Array.isArray(payload.data)) {
        array = payload.data;
      } else if (payload && Array.isArray(payload.candles)) {
        array = payload.candles;
      } else if (payload && payload.meta && payload.values) {
        // some formats: values array
        array = payload.values;
      } else {
        // maybe the backend returned single object or wrapper
        log('Unexpected candles payload shape:', payload);
        // try to find a first array within object
        for (const k in payload) {
          if (Array.isArray(payload[k])) {
            array = payload[k];
            break;
          }
        }
      }

      const mapped = mapCandlesToLW(array);
      if (!mapped.length) {
        log('No candle data returned from backend.');
        setBackendHealth('no-data', false);
        return;
      }

      candleSeries.setData(mapped);
      chart.timeScale().fitContent();
      setBackendHealth('ok', true);
      log(`Loaded ${mapped.length} candles for ${symbol} ${interval}`);
    } catch (err) {
      log('Error loading candles:', err);
      setBackendHealth('error', false);
    }
  }

  // health check
  async function checkHealth() {
    try {
      const r = await fetch(HEALTH_ENDPOINT, { cache: 'no-store' });
      if (r.ok) {
        const txt = await r.text();
        setBackendHealth('ok', true);
        log('Health OK:', txt);
      } else {
        setBackendHealth(`err ${r.status}`, false);
        log('Health fetch failed', r.status);
      }
    } catch (e) {
      setBackendHealth('offline', false);
      log('Health request error', e);
    }
  }

  // event wiring
  loadBtn.addEventListener('click', () => {
    const symbol = symbolInput.value.trim();
    const interval = intervalSelect.value;
    loadCandles(symbol, interval);
  });

  recreateBtn.addEventListener('click', () => recreateChart());

  checkHealthBtn.addEventListener('click', () => checkHealth());

  testApiBtn.addEventListener('click', async () => {
    const s = symbolInput.value.trim();
    const i = intervalSelect.value;
    const url = CANDLES_ENDPOINT(s, i);
    log('Testing API URL:', url);
    try {
      const r = await fetch(url, { cache: 'no-store' });
      const text = await r.text();
      log('API test response', r.status, text.slice ? text.slice(0, 2000) : text);
    } catch (e) {
      log('API test error:', e);
    }
  });

  autoBtn.addEventListener('click', () => {
    autoOn = !autoOn;
    autoBtn.textContent = `Auto: ${autoOn ? 'ON' : 'OFF'}`;
    if (autoOn) {
      // every 15s
      if (autoTimer) clearInterval(autoTimer);
      autoTimer = setInterval(() => {
        const s = symbolInput.value.trim();
        const i = intervalSelect.value;
        loadCandles(s, i);
      }, 15000);
      // run immediately
      loadBtn.click();
    } else {
      if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
    }
  });

  // initial setup
  (function init() {
    recreateChart();
    // pre-load example
    const initialSymbol = symbolInput.value.trim() || 'AAPL';
    const initialInterval = intervalSelect.value;
    // check backend
    checkHealth();
    // small delay then load
    setTimeout(() => loadCandles(initialSymbol, initialInterval), 400);
  })();

})();
