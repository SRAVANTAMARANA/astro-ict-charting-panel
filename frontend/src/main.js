// frontend/src/main.js
import { createChart } from 'lightweight-charts';

const chartDiv = document.getElementById('chart');
const symbolInput = document.getElementById('symbol');
const intervalSelect = document.getElementById('interval');
const loadBtn = document.getElementById('load');
const themeToggle = document.getElementById('theme');
const tvBtn = document.getElementById('tv');
const signalsBtn = document.getElementById('toggleSignals');
const signalsPanel = document.getElementById('signals');
const closeSignals = document.getElementById('closeSignals');
const signalsContent = document.getElementById('signalsContent');
const tvContainer = document.getElementById('tvContainer');

let chart = null;
let candleSeries = null;

function createOrRecreateChart(){
  if (chart && typeof chart.remove === 'function') {
    try { chart.remove(); } catch(e){ console.warn('chart remove failed', e); }
  } else {
    chartDiv.innerHTML = '';
  }

  const themeDark = !!themeToggle.checked;
  chart = createChart(chartDiv, {
    width: chartDiv.clientWidth,
    height: chartDiv.clientHeight,
    layout: {
      background: { color: themeDark ? '#0b1220' : '#ffffff' },
      textColor: themeDark ? '#dbeafe' : '#333'
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false }
  });

  candleSeries = chart.addCandlestickSeries();
  chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
    // optional hook
  });
}

window.addEventListener('resize', () => {
  if (chart && typeof chart.applyOptions === 'function') {
    chart.applyOptions({ width: chartDiv.clientWidth, height: chartDiv.clientHeight });
  }
});

async function loadAndRender(symbol, interval) {
  try {
    loadBtn.disabled = true;
    loadBtn.textContent = 'Loading…';
    const resp = await fetch(`/ict/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=500`);
    if (!resp.ok) {
      throw new Error('Server returned ' + resp.status);
    }
    const json = await resp.json();
    const candles = json.candles || json;
    candleSeries.setData(candles);
    loadBtn.textContent = 'Load';
    loadBtn.disabled = false;
  } catch (err) {
    console.error('Load error', err);
    loadBtn.textContent = 'Load';
    loadBtn.disabled = false;
    alert('Failed to load data: ' + err.message);
  }
}

loadBtn.addEventListener('click', () => {
  const symbol = symbolInput.value.trim() || 'XAUUSD';
  const interval = intervalSelect.value || '5min';
  createOrRecreateChart();
  loadAndRender(symbol, interval);
});

tvBtn.addEventListener('click', async () => {
  if (tvContainer.style.display === 'none' || !tvContainer.style.display) {
    tvContainer.style.display = 'block';
    tvContainer.innerHTML = '<div id="tv-widget" style="height:100%; width:100%"></div>';
    if (!window.TradingView) {
      const s = document.createElement('script');
      s.src = 'https://s3.tradingview.com/tv.js';
      s.onload = () => initTV();
      document.head.appendChild(s);
    } else {
      initTV();
    }
  } else {
    tvContainer.style.display = 'none';
    tvContainer.innerHTML = '';
  }
});

function initTV(){
  try {
    // tradingview widget
    new TradingView.widget({
      container_id: 'tv-widget',
      symbol: symbolInput.value || 'XAUUSD',
      interval: intervalSelect.value || '5',
      width: '100%', height: '100%',
      toolbar_bg: '#f1f3f6',
      theme: themeToggle.checked ? 'Dark' : 'Light'
    });
  } catch(e) {
    console.error('TradingView init error', e);
  }
}

signalsBtn.addEventListener('click', () => {
  signalsPanel.style.display = signalsPanel.style.display === 'block' ? 'none' : 'block';
});
closeSignals.addEventListener('click', () => { signalsPanel.style.display = 'none'; });

// initial
createOrRecreateChart();
loadAndRender(symbolInput.value, intervalSelect.value);
