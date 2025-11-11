// server.js
// Combined: WebSocket signaling (ws://localhost:8080) + image bridge (http://localhost:5175)
//
// - Signaling: same behavior you had before (forward JSON messages by "to" id)
// - Bridge: watches ./data/temp# folders, serves newest frame + SSE events
//
// Endpoints:
//   GET  /live/latest-temp                 -> { folder: "tempN" }
//   GET  /live/events(?folder=tempN)       -> SSE "new-frame" events
//   GET  /live/frame(?folder=tempN)        -> newest image bytes
//   GET  /frames/tempN/<file>              -> static browse

// server.js (CommonJS version)
const express = require("express");
const http = require("http");
const path = require("path");
const fs = require("fs");
const chokidar = require("chokidar");
const compression = require("compression");
const morgan = require("morgan");
const cors = require("cors");
const { WebSocketServer, WebSocket } = require("ws");
const crypto = require("crypto");


// ----------------------------
// WebSocket signaling (8080)
// ----------------------------
const WS_PORT = process.env.WS_PORT || 8080;
const wsServer = new WebSocketServer({ port: WS_PORT });
console.log(`🛰️  WebSocket server listening on ws://localhost:${WS_PORT}`);

// Track all connected clients
const clients = new Map(); // id -> ws

wsServer.on("connection", (ws) => {
  const id = crypto.randomUUID();
  clients.set(id, ws);
  ws.send(JSON.stringify({ type: "welcome", id }));

  ws.on("message", (raw) => {
    try {
      const { to, type, payload } = JSON.parse(raw);
      const dest = clients.get(to);
      if (dest && dest.readyState === WebSocket.OPEN) {
        dest.send(JSON.stringify({ from: id, type, payload }));
      }
    } catch (e) {
      // ignore malformed
    }
  });

  ws.on("close", () => {
    clients.delete(id);
  });
});

// ----------------------------
// Image bridge (5175)
// ----------------------------
const app = express();
app.use(compression());
app.use(morgan("dev"));
app.use(cors());

const REPO_ROOT = process.cwd();                   // run from repo root
const DATA_ROOT = path.resolve(REPO_ROOT, "data"); // ./data
const HTTP_PORT = process.env.BRIDGE_PORT || 5175;

const TEMP_RE = /^temp(\d+)$/i;
const IMG_RE = /\.(png|jpe?g|webp)$/i;

// State: per-folder latest file + SSE clients
const latestByFolder = new Map(); // folderName -> latest filename
const sseByFolder = new Map();    // folderName -> Set(res)

fs.mkdirSync(DATA_ROOT, { recursive: true });

function getLatestTempFolder() {
  const entries = fs.readdirSync(DATA_ROOT, { withFileTypes: true })
    .filter(d => d.isDirectory() && TEMP_RE.test(d.name))
    .map(d => {
      const p = path.join(DATA_ROOT, d.name);
      return { name: d.name, t: fs.statSync(p).mtimeMs };
    })
    .sort((a, b) => a.t - b.t);
  return entries.length ? entries.at(-1).name : null;
}

function ensureFolderSetup(folder) {
  if (!folder) return;
  if (!sseByFolder.has(folder)) sseByFolder.set(folder, new Set());

  if (!latestByFolder.has(folder)) {
    const dir = path.join(DATA_ROOT, folder);
    if (fs.existsSync(dir)) {
      const files = fs.readdirSync(dir)
        .filter(f => IMG_RE.test(f))
        .map(f => ({ f, t: fs.statSync(path.join(dir, f)).mtimeMs }))
        .sort((a, b) => a.t - b.t);
      if (files.length) latestByFolder.set(folder, files.at(-1).f);
    }
  }
}

// Watch ./data/temp#/*
const watcher = chokidar.watch(DATA_ROOT, { ignoreInitial: true, depth: 1 });

watcher.on("addDir", (dirPath) => {
  const folder = path.basename(dirPath);
  if (TEMP_RE.test(folder)) {
    ensureFolderSetup(folder);
    console.log(`[bridge] New folder: ${folder}`);
  }
});

watcher.on("add", (filePath) => {
  const folder = path.basename(path.dirname(filePath));
  const fname = path.basename(filePath);
  if (!TEMP_RE.test(folder) || !IMG_RE.test(fname)) return;

  latestByFolder.set(folder, fname);

  const clients = sseByFolder.get(folder);
  if (clients && clients.size) {
    const payload = `data: ${JSON.stringify({ type: "new-frame", folder, file: fname, ts: Date.now() })}\n\n`;
    clients.forEach(res => res.write(payload));
  }
});

// Routes
app.get("/live/latest-temp", (req, res) => {
  res.json({ folder: getLatestTempFolder() });
});

app.get("/live/events", (req, res) => {
  let { folder } = req.query;
  if (!folder) folder = getLatestTempFolder();
  if (!folder) return res.status(404).end("No temp# folder found");

  ensureFolderSetup(folder);

  res.set({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  res.flushHeaders();

  const bucket = sseByFolder.get(folder);
  bucket.add(res);

  const latest = latestByFolder.get(folder);
  if (latest) {
    res.write(`data: ${JSON.stringify({ type: "new-frame", folder, file: latest, ts: Date.now() })}\n\n`);
  }

  req.on("close", () => bucket.delete(res));
});

app.get("/live/frame", (req, res) => {
  let { folder } = req.query;
  if (!folder) folder = getLatestTempFolder();
  if (!folder) return res.status(404).end("No temp# folder found");

  ensureFolderSetup(folder);
  const latest = latestByFolder.get(folder);
  if (!latest) return res.status(404).end("No frames yet");

  const abs = path.join(DATA_ROOT, folder, latest);
  const ext = path.extname(abs).toLowerCase();
  const mime = ext === ".png" ? "image/png" : ext === ".webp" ? "image/webp" : "image/jpeg";
  res.setHeader("Content-Type", mime);
  fs.createReadStream(abs).pipe(res);
});

// optional: static browse under /frames
app.use("/frames", express.static(DATA_ROOT, { maxAge: 0, etag: true }));

const httpServer = http.createServer(app);
httpServer.listen(HTTP_PORT, () => {
  console.log(`[bridge] Serving data root: ${DATA_ROOT}`);
  console.log(`[bridge] Latest temp: ${getLatestTempFolder() || "—"}`);
  console.log(`[bridge] http://localhost:${HTTP_PORT}/live/latest-temp`);
  console.log(`[bridge] http://localhost:${HTTP_PORT}/live/events`);
  console.log(`[bridge] http://localhost:${HTTP_PORT}/live/frame`);
});

