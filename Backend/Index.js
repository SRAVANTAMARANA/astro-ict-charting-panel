const express = require('express');
const app = express();

// health route that nginx should proxy to
app.get('/ict/health', (req, res) => {
  res.json({ status: "ok", service: "backend", time: new Date().toISOString() });
});

// a small sample endpoint optionally used by charts
app.get('/ict/time_series', (req, res) => {
  res.json({ data: [], message: "sample" });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`backend started on ${PORT}`));
