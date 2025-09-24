// frontend/app.js

(function () {
  // check library
  const lib = window.LightweightCharts;
  if (!lib || typeof lib.createChart !== 'function') {
    console.error('LightweightCharts not found (window.LightweightCharts). Did you load the UMD script?');
    document.getElementById('status').innerText = 'Status: LightweightCharts missing';
    return;
  }

  const createChart = lib.createChart;
  const chartRoot = document.getElementById('chart-root');
  let chart = null;
  let candleSeries = null;

  function createNewChart() {
    if (chart) {
      try { chart.remove(); } catch (e) { console.warn('remove failed', e); }
      chart = null;
      candleSeries = null;
    }

    chart = createChart(chartRoot, {
      width: chartRoot.clientWidth,
      height: chartRoot.clientHeight,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false }
    });

    candleSeries = chart.addCandlestickSeries(); // this should exist
    chart.timeScale().fitContent();
  }

  // handle window resize
  window.addEventListener('resize', () => {
    if (chart) {
      chart.applyOptions({ width: chartRoot.clientWidth, height: chartRoot.clientHeight });
    }
  });

  // sample: convert TwelveData time_series response to candlesticks
  function convertTwelveDataToCandles(twDataArray) {
    // twDataArray is array of objects with datetime, open, high, low, close, volume
    return twDataArray.map(item => {
      // LightweightCharts expects timestamp or ISO string in time
      // Use ISO date/time (or 'yyyy-mm-dd HH:mm:ss' depending on input)
      return {
        time: item.datetime, // string ISO is OK in latest versions
        open: parseFloat(item.open),
        high: parseFloat(item.high),
        low: parseFloat(item.low),
        close: parseFloat(item.close)
      };
    }).reverse(); // TwelveData returns most recent first; LightweightCharts expects chronological order
  }

  // load data from TwelveData (example)
  async function loadFromTwelveData(symbol, interval) {
    document.getElementById('status').innerText = 'Status: loading...';
    try {
      // Replace this URL with your real TwelveData or API endpoint & key
      // For debugging you used: https://api.twelvedata.com/time_series?apikey=KEY&symbol=AAPL&interval=1min
      const key = '55a08a202ca740589278abe23d94436a'; // example key you posted earlier (keep secure)
      const url = `https://api.twelvedata.com/time_series?apikey=${key}&symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&outputsize=100&format=JSON`;
      const res = await fetch(url);
      const json = await res.json();
      if (json.status === 'error' || json.code === 404 || !json.values) {
        console.error('API error', json);
        document.getElementById('status').innerText = 'Status: API error - see console';
        return;
      }
      const values = json.values; // array
      const candles = convertTwelveDataToCandles(values);
      candleSeries.setData(candles);
      chart.timeScale().fitContent();
      document.getElementById('status').innerText = `Status: loaded ${candles.length} bars`;
    } catch (err) {
      console.error(err);
      document.getElementById('status').innerText = 'Status: load failed';
    }
  }

  // wire controls
  document.getElementById('load').addEventListener('click', () => {
    const symbol = document.getElementById('symbol').value.trim();
    const interval = document.getElementById('interval').value;
    if (!symbol) {
      alert('Please enter a symbol');
      return;
    }
    // ensure chart exists
    if (!chart) createNewChart();
    loadFromTwelveData(symbol, interval);
  });

  // initial chart
  createNewChart();

  // for debug: set a small sample if API access is blocked
  const sample = [
    { time: '2025-09-24T02:11:13.357Z', open: 1900.3, high: 1900.9, low: 1899.7, close: 1899.4 },
    { time: '2025-09-24T02:12:13.357Z', open: 1900.3, high: 1900.6, low: 1899.7, close: 1900.3 },
    { time: '2025-09-24T02:13:13.357Z', open: 1900.4, high: 1901.0, low: 1899.8, close: 1900.9 }
  ];
  // candleSeries.setData(sample.reverse()); // uncomment to test static sample
})();
