const http = require('http');
const { getBridgeState } = require('./pairingBridge');

let server = null;

function json(res, statusCode, payload) {
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(JSON.stringify(payload, null, 2));
}

function startWebServer() {
  if (server) return server;

  const port = Number(process.env.PORT || 3000);
  const host = '0.0.0.0';

  server = http.createServer((req, res) => {
    const state = getBridgeState();
    const payload = {
      ok: true,
      service: 'KnightBot-MD',
      connectionState: state.connectionState,
      hasSocket: state.hasSocket,
      user: state.user,
      lastUpdatedAt: state.lastUpdatedAt,
      uptimeSeconds: Math.floor(process.uptime()),
      timestamp: new Date().toISOString(),
    };

    if (req.url === '/health' || req.url === '/status' || req.url === '/') {
      return json(res, 200, payload);
    }

    return json(res, 404, {
      ok: false,
      message: 'Not found',
      path: req.url,
    });
  });

  server.on('error', (error) => {
    console.error('Web server error:', error.message);
  });

  server.listen(port, host, () => {
    console.log(`🌐 Web server listening on ${host}:${port}`);
  });

  return server;
}

module.exports = {
  startWebServer,
};
