/**
 * Screenshot & Notes dev server for TestModel.
 *
 * Usage: node scripts/screenshot-server.js
 *
 * Receives screenshots and notes from the app, saves them to
 * the screenshots/ directory with metadata JSON files.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 8766;
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'screenshots');

// Ensure screenshots directory exists
if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

const server = http.createServer((req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  if (req.method === 'POST' && req.url === '/screenshot') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const timestamp = new Date().toISOString().replace(/:/g, '-');
        const baseName = `${timestamp}_testmodel`;

        // Save metadata
        const metaPath = path.join(SCREENSHOTS_DIR, `${baseName}.json`);
        fs.writeFileSync(metaPath, JSON.stringify(data.meta || {}, null, 2));
        console.log(`[${new Date().toLocaleTimeString()}] Saved: ${baseName}.json`);

        // Save image if present
        if (data.image) {
          const imgPath = path.join(SCREENSHOTS_DIR, `${baseName}.jpg`);
          const imgBuffer = Buffer.from(data.image, 'base64');
          fs.writeFileSync(imgPath, imgBuffer);
          console.log(`[${new Date().toLocaleTimeString()}] Saved: ${baseName}.jpg (${(imgBuffer.length / 1024).toFixed(0)} KB)`);
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (err) {
        console.error('Error processing request:', err.message);
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Screenshot server listening on http://0.0.0.0:${PORT}/screenshot`);
  console.log(`Screenshots saved to: ${SCREENSHOTS_DIR}`);
});
