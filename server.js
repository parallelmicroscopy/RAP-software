// server.js  (CommonJS version)
// - WebSocket signaling (ws://localhost:8080)
// - Image bridge w/ TIFF→PNG on http://localhost:5175
// - Serves your front-end from repo root

const express = require("express");
const { WebSocketServer, WebSocket } = require("ws");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const app = express();
const PORT = 5175;

// -----------------------------
// 📁 1. Image bridge
// -----------------------------
const DATA_ROOT = path.resolve("./data");
console.log(`[bridge] Serving data root: ${DATA_ROOT}`);

function getTempFolders() {
  return fs
    .readdirSync(DATA_ROOT, { withFileTypes: true })
    .filter(d => d.isDirectory() && d.name.startsWith("temp"))
    .map(d => d.name)
    .sort((a, b) => {
      const aStat = fs.statSync(path.join(DATA_ROOT, a));
      const bStat = fs.statSync(path.join(DATA_ROOT, b));
      return bStat.mtimeMs - aStat.mtimeMs;
    });
}

function getLatestTempFolder() {
  const all = getTempFolders();
  return all[0] || null;
}

app.get("/live/latest-temp", (req, res) => {
  const folder = getLatestTempFolder();
  if (!folder) return res.status(404).json({ error: "No temp folder" });
  res.json({ folder });
});

// watcher + SSE state
const watchers = new Map();
const latestByFolder = new Map();
const sseClients = new Map();

function ensureFolderSetup(folder) {
  const abs = path.join(DATA_ROOT, folder);
  if (watchers.has(folder)) return;
  const w = fs.watch(abs, (event, fname) => {
    if (fname && /\.(png|jpe?g|webp|tif|tiff)$/i.test(fname)) {
      latestByFolder.set(folder, fname);
      sendSSE(folder, fname);
    }
  });
  watchers.set(folder, w);
  console.log(`[bridge] watching ${folder}`);
}

function sendSSE(folder, msg) {
  const set = sseClients.get(folder);
  if (!set) return;
  for (const res of set) res.write(`data: ${msg}\n\n`);
}

app.get("/live/events", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.flushHeaders();

  const folder = req.query.folder || getLatestTempFolder();
  if (!folder) return res.end();

  ensureFolderSetup(folder);
  if (!sseClients.has(folder)) sseClients.set(folder, new Set());
  sseClients.get(folder).add(res);

  req.on("close", () => {
    sseClients.get(folder)?.delete(res);
  });
});

app.get("/live/frame", async (req, res) => {
  let { folder } = req.query;
  if (!folder) folder = getLatestTempFolder();
  if (!folder) return res.status(404).end("No temp folder found");
  ensureFolderSetup(folder);

  const latest = latestByFolder.get(folder);
  if (!latest) return res.status(404).end("No frames yet");

  const abs = path.join(DATA_ROOT, folder, latest);
  const ext = path.extname(abs).toLowerCase();

  try {
    if (ext === ".tif" || ext === ".tiff") {
      res.setHeader("Content-Type", "image/png");
      return sharp(abs).png().pipe(res);
    } else if (ext === ".png") {
      res.setHeader("Content-Type", "image/png");
    } else if (ext === ".jpg" || ext === ".jpeg") {
      res.setHeader("Content-Type", "image/jpeg");
    } else if (ext === ".webp") {
      res.setHeader("Content-Type", "image/webp");
    } else {
      return res.status(400).end("Unsupported format");
    }
    fs.createReadStream(abs).pipe(res);
  } catch (err) {
    console.error("[bridge] frame send error", err);
    res.status(500).end("error");
  }
});

// serve front-end (index.html, main.js, etc.)
app.use("/", express.static(process.cwd(), { maxAge: 0, etag: true }));

// -----------------------------
// 🛰️ 2. WebSocket signaling
// -----------------------------
const WS_PORT = process.env.WS_PORT || 8080;
const wss = new WebSocketServer({ port: WS_PORT });
console.log(`🛰️  WebSocket server listening on ws://localhost:${WS_PORT}`);

const clients = new Map();
wss.on("connection", ws => {
  const id = crypto.randomUUID();
  clients.set(id, ws);
  ws.send(JSON.stringify({ type: "welcome", id }));

  ws.on("message", msg => {
    try {
      const { to, type, payload } = JSON.parse(msg);
      const dest = clients.get(to);
      if (dest && dest.readyState === ws.OPEN) {
        dest.send(JSON.stringify({ from: id, type, payload }));
      }
    } catch (e) {
      console.error("bad msg", e);
    }
  });

  ws.on("close", () => clients.delete(id));
});

// -----------------------------
app.listen(PORT, () => {
  console.log(`[bridge] HTTP server running at http://localhost:${PORT}`);
  const latest = getLatestTempFolder();
  console.log(`[bridge] Latest temp: ${latest}`);
  console.log(`[bridge] Try: http://localhost:${PORT}/live/latest-temp`);
  console.log(`[bridge] Try: http://localhost:${PORT}/live/frame`);
});
