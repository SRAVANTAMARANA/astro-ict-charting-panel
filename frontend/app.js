// app.js
let chart;
let candleSeries;

async function recreateChart() {
  const chartDiv = document.getElementById("chart");

  // Clear any existing chart
  if (chart) {
    chart.remove();
  }

  // ✅ Use LightweightCharts global from standalone script
  chart = LightweightCharts.createChart(chartDiv, {
    width: chartDiv.clientWidth,
    height: chartDiv.clientHeight,
    layout: {
      background: { color: "#ffffff" },
      textColor: "#333",
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
  });

  // ✅ Create candlestick series correctly
  candleSeries = chart.addCandlestickSeries();

  // Load candles
  await loadCandles();
}

async function loadCandles() {
  const symbol = document.getElementById("symbol").value || "AAPL";
  const interval = document.getElementById("interval").value || "1min";

  try {
    const res = await fetch(
      `http://localhost:8000/ict/candles?symbol=${symbol}&interval=${interval}&limit=100`
    );
    const data = await res.json();

    if (!data || !data.length) {
      console.warn("No data received");
      return;
    }

    // ✅ Transform to {time, open, high, low, close}
    const formatted = data.map(d => ({
      time: Math.floor(new Date(d.time).getTime() / 1000),
      open: parseFloat(d.open),
      high: parseFloat(d.high),
      low: parseFloat(d.low),
      close: parseFloat(d.close),
    }));

    candleSeries.setData(formatted);
    chart.timeScale().fitContent();
  } catch (err) {
    console.error("Error loading candles", err);
  }
}

// Resize handler
window.addEventListener("resize", () => {
  if (chart) {
    const chartDiv = document.getElementById("chart");
    chart.applyOptions({
      width: chartDiv.clientWidth,
      height: chartDiv.clientHeight,
    });
  }
});

// Initialize on page load
window.addEventListener("DOMContentLoaded", recreateChart);
