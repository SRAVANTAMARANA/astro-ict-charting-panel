let chart, candleSeries;
let dark = false;
const chartDiv = document.getElementById("chart");

function recreateChart() {
  if (chart) chart.remove();

  chart = LightweightCharts.createChart(chartDiv, {
    width: chartDiv.clientWidth,
    height: chartDiv.clientHeight,
    layout: {
      background: { color: dark ? "#0b1220" : "#ffffff" },
      textColor: dark ? "#dbeafe" : "#333",
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
  });

  candleSeries = chart.addCandlestickSeries();
}

async function loadData() {
  const symbol = document.getElementById("symbol").value;
  const interval = document.getElementById("interval").value;
  document.getElementById("status").innerText = "Status: loading...";

  try {
    // ✅ Always fetch from backend:8000
    const res = await fetch(
      `http://localhost:8000/ict/candles?symbol=${symbol}&interval=${interval}&limit=100`
    );
    const data = await res.json();

    if (data.candles) {
      const formatted = data.candles.map(c => ({
        time: Math.floor(new Date(c.time).getTime() / 1000),
        open: parseFloat(c.open),
        high: parseFloat(c.high),
        low: parseFloat(c.low),
        close: parseFloat(c.close),
      }));
      recreateChart();
      candleSeries.setData(formatted);
      document.getElementById("status").innerText = "Status: loaded";
    } else {
      document.getElementById("status").innerText = "Status: no data";
    }
  } catch (err) {
    console.error(err);
    document.getElementById("status").innerText = "Status: error";
  }
}

function toggleDark() {
  dark = !dark;
  recreateChart();
}

// Resize support
window.addEventListener("resize", () => {
  if (chart) {
    chart.applyOptions({
      width: chartDiv.clientWidth,
      height: chartDiv.clientHeight,
    });
  }
});

// init
recreateChart();
