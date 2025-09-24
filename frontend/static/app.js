// frontend/static/app.js
document.addEventListener('DOMContentLoaded', () => {
  // Use UMD global from the standalone bundle
  const LightweightCharts = window.LightweightCharts;
  if (!LightweightCharts || !LightweightCharts.createChart) {
    console.error('LightweightCharts not loaded');
    document.getElementById('status').innerText = 'Status: charts lib failed to load';
    return;
  }

  const chartDiv = document.getElementById('chart');
  const statusEl = document.getElementById('status');
  const symbolInput = document.getElementById('symbol');
  const intervalSelect = document.getElementById('interval');
  const loadBtn = document.getElementById('loadBtn');

  // Chart + series
  let chart = null;
  let candleSeries = null;

  function createChart() {
    // Remove old chart container children (safety)
    chartDiv.innerHTML = '';
    chart = LightweightCharts.createChart(chartDiv, {
      width: chartDiv.clientWidth,
      height: chartDiv.clientHeight,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333'
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });

    candleSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickVisible: true,
    });

    // Resize handling
    window.addEventListener('resize', () => {
      if (chart) {
        chart.applyOptions({
          width: chartDiv.clientWidth,
          height: chartDiv.clientHeight
        });
      }
    });
  }

  // Convert your backend data to library format {time, open, high, low, close, volume?}
  function mapCandles(serverData) {
    // serverData expected to be array of objects like { time: "YYYY-MM-DDTHH:mm:ss", open: "...", high: "...", low: "...", close: "..."}
    return serverData.map(d => ({
      time: d.time,                 // if backend returns ISO (yyyy-mm-ddTHH:MM:SSZ) that's OK
      open: parseFloat(d.open),
      high: parseFloat(d.high),
      low: parseFloat(d.low),
      close: parseFloat(d.close)
    }));
  }

  async function loadCandles() {
    const symbol = (symbolInput.value || 'AAPL').trim();
    const interval = intervalSelect.value || '1min';

    statusEl.innerText = `Status: loading ${symbol} ${interval}...`;

    try {
      // **IMPORTANT**: This hits **/ict/candles** (relative) which we will proxy to backend:8000 in nginx
      const url = `/ict/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=200`;
      const resp = await fetch(url, { cache: 'no-store' });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`HTTP ${resp.status} ${resp.statusText} - ${txt}`);
      }
      const j = await resp.json();

      // Backend expected to return { symbol: 'AAPL', candles: [...] } or just array; handle both
      let candles = j.candles || j.data || j;
      if (!Array.isArray(candles)) throw new Error('Unexpected candles response');

      const seriesData = mapCandles(candles);
      if (!chart || !candleSeries) {
        createChart();
      }
      candleSeries.setData(seriesData);
      statusEl.innerText = `Status: loaded ${seriesData.length} bars for ${symbol}`;
    } catch (err) {
      console.error('Load candles failed', err);
      statusEl.innerText = `Error: ${err.message}`;
    }
  }

  // init
  createChart();

  loadBtn.addEventListener('click', () => loadCandles());

  // optional: load immediately
  loadCandles();
});
