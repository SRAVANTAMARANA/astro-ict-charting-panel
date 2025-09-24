const express = require('express');
const fetch = require('node-fetch');
const app = express();
const PORT = process.env.PORT || 8000;

app.get('/ict/health', (req, res) => {
  res.json({ status: 'ok', service: 'backend', time: new Date().toISOString() });
});

// optional proxy endpoint to TwelveData
app.get('/ict/time_series', async (req, res) => {
  const apiKey = process.env.TWELVE_API_KEY;
  const symbol = req.query.symbol || 'AAPL';
  const interval = req.query.interval || '1min';
  if (!apiKey) {
    // return sample data if no API key provided
    return res.json({
      status: 'demo',
      symbol,
      interval,
      data: [
        { datetime: new Date().toISOString(), open: 100, high: 102, low: 99, close: 101, volume: 1234 }
      ]
    });
  }

  // proxy request to TwelveData
  const url = `https://api.twelvedata.com/time_series?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&apikey=${encodeURIComponent(apiKey)}&outputsize=30`;
  try {
    const rr = await fetch(url);
    const body = await rr.text();
    // forward the remote response as-is
    res.type('application/json').status(rr.status).send(body);
  } catch (err) {
    res.status(500).json({ error: 'proxy_failed', details: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`backend listening on ${PORT}`);
});
