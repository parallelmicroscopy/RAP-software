// latestTempStream.js
//
// Usage:
//   import { liveImageStreamFromLatestTemp } from "./latestTempStream.js";
//
//   const { stream, stop } = await liveImageStreamFromLatestTemp({
//     bridgeBase: "http://localhost:5175",
//     fps: 12,
//     width: 1280,
//     height: 720,
//   });
//   videoEl.srcObject = stream; // e.g., preview3
//
// Requirements (server):
//   GET  /live/latest-temp                -> { folder: "temp7" }
//   GET  /live/events?folder=<tempN>      -> text/event-stream (SSE)
//   GET  /live/frame?folder=<tempN>       -> newest image bytes (png/jpg/webp)

export async function liveImageStreamFromLatestTemp({
    bridgeBase = "http://localhost:5175",
    fps = 12,
    width = 1280,
    height = 720,
    // Optional backoff when folder switches or fetch fails
    retryMs = 750,
  } = {}) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
  
    const img = new Image();
    img.crossOrigin = "anonymous";
  
    let currentFolder = null;
    let es = null;
    let lastBlobUrl = null;
    let fetching = false;
    let closed = false;
  
    function revokeOld() {
      if (lastBlobUrl) {
        URL.revokeObjectURL(lastBlobUrl);
        lastBlobUrl = null;
      }
    }
  
    async function fetchLatestFolder() {
      const url = `${bridgeBase}/live/latest-temp`;
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`latest-temp failed: ${res.status}`);
      const { folder } = await res.json();
      if (!folder) throw new Error("latest-temp: no folder returned");
      return folder;
    }
  
    async function fetchAndDraw() {
      if (fetching || closed) return;
      fetching = true;
      try {
        const res = await fetch(
          `${bridgeBase}/live/frame?folder=${encodeURIComponent(currentFolder)}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error(`frame fetch failed: ${res.status}`);
        const blob = await res.blob();
        revokeOld();
        lastBlobUrl = URL.createObjectURL(blob);
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
          img.src = lastBlobUrl;
        });
        ctx.drawImage(img, 0, 0, width, height);
      } catch (e) {
        // soft fail; will retry on next event or timer
        // console.debug("[latestTemp] fetch/draw error", e);
      } finally {
        fetching = false;
      }
    }
  
    function attachSSE() {
      if (es) {
        try { es.close(); } catch {}
        es = null;
      }
      es = new EventSource(
        `${bridgeBase}/live/events?folder=${encodeURIComponent(currentFolder)}`
      );
      es.addEventListener("message", () => fetchAndDraw());
      es.addEventListener("error", () => {
        // Connection hiccup: try to reattach shortly
        if (closed) return;
        try { es.close(); } catch {}
        es = null;
        setTimeout(() => {
          if (!closed) attachSSE();
        }, retryMs);
      });
    }
  
    async function ensureFolderAndSSE() {
      try {
        const latest = await fetchLatestFolder();
        if (currentFolder !== latest) {
          currentFolder = latest;
          attachSSE();
          // draw once immediately in case no event arrives
          await fetchAndDraw();
        }
      } catch {
        // Couldn’t get folder: retry soon
        if (!closed) setTimeout(ensureFolderAndSSE, retryMs);
      }
    }
  
    // Kick things off
    await ensureFolderAndSSE();
  
    // Re-check if writer switches to a newer temp# (e.g., new run)
    const folderPoll = setInterval(() => {
      if (!closed) ensureFolderAndSSE();
    }, 5000);
  
    const stream = canvas.captureStream(fps);
  
    // graceful cleanup
    function stop() {
      closed = true;
      clearInterval(folderPoll);
      if (es) {
        try { es.close(); } catch {}
        es = null;
      }
      revokeOld();
      stream.getTracks().forEach(t => t.stop());
    }
  
    // monkey-patch track.stop to also close SSE if caller stops tracks directly
    stream.getTracks().forEach(t => {
      const orig = t.stop.bind(t);
      t.stop = () => { stop(); orig(); };
    });
  
    return { stream, canvas, stop };
  }
  