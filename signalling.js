// signalling.js
export class Signaler {
  constructor({ room, url = "ws://localhost:8080" } = {}) {
    this.url = url;
    this.room = room || "default-room";
    this.ws = null;
    this.id = null;
    this.onMessage = null; // set by main.js
    this.peerId = null;    // auto-filled from first incoming message
  }

  connect() {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(this.url);
      this.ws = ws;

      ws.onopen = () => {
        // join the room so the server knows where to broadcast
        ws.send(JSON.stringify({ type: "join", payload: { room: this.room } }));
        resolve();
      };

      ws.onerror = (e) => reject(new Error("WebSocket error"));

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "welcome" && msg.id) {
            this.id = msg.id;
            return;
          }
          // remember who contacted us first (so streamer can reply)
          if (msg.from && !this.peerId) this.peerId = msg.from;

          if (this.onMessage) this.onMessage(msg);
        } catch {
          /* ignore malformed */
        }
      };
    });
  }

  // Send to a specific peer (if known), otherwise broadcast within room
  send(obj, toId = this.peerId) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    const payload = toId
      ? { to: toId, type: obj.type, payload: { ...obj } }
      : { room: this.room, type: obj.type, payload: { ...obj } };
    this.ws.send(JSON.stringify(payload));
  }
}
