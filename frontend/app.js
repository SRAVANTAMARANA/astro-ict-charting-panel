<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Astro ICT Chart Panel</title>
  <link rel="stylesheet" href="/static/styles.css" />
  <style>
    body { font-family: Arial, sans-serif; margin: 0; }
    #container { display:flex; gap:12px; padding:12px;}
    #left { width: 70%; }
    #right { width: 30%; max-width: 420px; }
    #chart { height: 560px; width: 100%; background:#fff; border:1px solid #ddd; }
    .controls { margin-bottom: 8px; }
    .status { font-size:12px; color:#666; margin-top:8px; }
    button { padding:6px 10px; }
    input, select { padding:6px; }
  </style>
</head>
<body>
  <div id="container">
    <div id="left">
      <h2>Astro ICT Chart Panel</h2>
      <div id="chart"></div>
      <div class="status" id="status">Status: idle</div>
    </div>

    <div id="right">
      <div class="controls">
        <label>Symbol: <input id="symbol" value="AAPL" /></label><br/>
        <label>Interval:
          <select id="interval">
            <option value="1min">1m</option>
            <option value="5min">5m</option>
            <option value="15min">15m</option>
            <option value="1h">1h</option>
            <option value="1day">1d</option>
          </select>
        </label>
      </div>

      <div class="controls">
        <button id="loadBtn">Load</button>
        <button id="tvBtn">TV Style (toggle)</button>
      </div>

      <div>
        <h3>Signals</h3>
        <div id="signals">AI mentor demo text</div>
      </div>
    </div>
  </div>

  <!-- Lightweight Charts UMD standalone (Production) -->
  <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>

  <!-- App logic -->
  <script src="/static/app.js"></script>
</body>
</html>
