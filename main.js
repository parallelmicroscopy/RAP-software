// main.js
// Role-based WebRTC with a single displayed stream.
// Streamer: publishes exactly one track (the image-stream canvas).
// Viewer  : receives exactly one track and displays it.

import { Signaler } from "./signalling.js";
// Choose ONE of these, depending on what you implemented:
import { liveImageStreamFromBridge } from "./stream.js";
// import { liveImageStreamFromLatestTemp } from "./latestTempStream.js";

const ui = {
  roleSelect: document.getElementById("roleSelect"),     // <select id="roleSelect"> streamer|viewer
  roomInput:  document.getElementById("roomInput"),      // <input  id="roomInput"  placeholder="room">
  initBtn:    document.getElementById("initButton"),     // <button id="initButton">Initialize</button>
  startBtn:   document.getElementById("startStream"),    // <button id="startStream">Start Streaming</button>
  videoEl:    document.getElementById("preview"),        // <video   id="preview"   playsinline autoplay muted>
  statusEl:   document.getElementById("status"),         // <div     id="status"></div> (optional)
};

const ICE_SERVERS = [
  { urls: "stun:stun.l.google.com:19302" },
];

let role = "viewer";
let pc = null;
let signaler = null;
let localStream = null;
let started = false;

function logStatus(msg) {
  if (ui.statusEl) ui.statusEl.textContent = msg;
  console.log("[main]", msg);
}

function getRoom() {
  const value = (ui.roomInput?.value || "").trim();
  return value || "default-room";
}

function createPeerConnection() {
  if (pc) { try { pc.close(); } catch {}; }
  pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

  // Display only the first remote stream
  pc.ontrack = (ev) => {
    logStatus("Remote track received");
    // One remote MediaStream
    if (ui.videoEl && !ui.videoEl.srcObject) {
      const remoteStream = ev.streams[0] || new MediaStream([ev.track]);
      ui.videoEl.srcObject = remoteStream;
    }
  };

  pc.onicecandidate = ({ candidate }) => {
    if (candidate) signaler?.send({ type: "candidate", candidate });
  };

  pc.onconnectionstatechange = () => {
    logStatus(`PeerConnection state: ${pc.connectionState}`);
  };

  return pc;
}

async function attachLocalImageStream() {
  // Choose the source helper you prefer:
  // const live = await liveImageStreamFromLatestTemp({ bridgeBase: "http://localhost:5175", fps: 12, width: 1280, height: 720 });
  const live = await liveImageStreamFromBridge({ bridgeBase: "http://localhost:5175", fps: 12, width: 1280, height: 720 });

  localStream = live.stream;

  // OPTIONAL: show the local preview to the streamer only
  if (role === "streamer" && ui.videoEl) {
    ui.videoEl.srcObject = localStream;
    ui.videoEl.muted = true; // just in case
  }
  return live;
}

async function startAsStreamer() {
  if (started) return;
  started = true;

  createPeerConnection();

  // Get the image stream (canvas.captureStream)
  await attachLocalImageStream();

  // Publish exactly one stream (one track)
  for (const track of localStream.getTracks()) {
    pc.addTrack(track, localStream);
    break; // ensure only one track (video) is added even if more exist
  }

  const offer = await pc.createOffer({ offerToReceiveAudio: false, offerToReceiveVideo: true });
  await pc.setLocalDescription(offer);
  signaler.send({ type: "offer", sdp: offer.sdp });

  logStatus("Streamer: offer sent");
}

async function startAsViewer() {
  if (started) return;
  started = true;

  createPeerConnection();
  logStatus("Viewer: waiting for offer...");
}

async function handleSignalMessage(msg) {
  if (!pc) createPeerConnection();

  switch (msg.type) {
    case "offer": {
      if (role !== "viewer") return;
      logStatus("Viewer: offer received, creating answer...");
      await pc.setRemoteDescription({ type: "offer", sdp: msg.sdp });
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      signaler.send({ type: "answer", sdp: answer.sdp });
      logStatus("Viewer: answer sent");
      break;
    }
    case "answer": {
      if (role !== "streamer") return;
      logStatus("Streamer: answer received");
      await pc.setRemoteDescription({ type: "answer", sdp: msg.sdp });
      break;
    }
    case "candidate": {
      if (!msg.candidate) return;
      try {
        await pc.addIceCandidate(msg.candidate);
      } catch (e) {
        console.warn("Error adding ICE candidate", e);
      }
      break;
    }
    default:
      break;
  }
}

async function init() {
  role = (ui.roleSelect?.value || "viewer").toLowerCase();
  const room = getRoom();

  signaler = new Signaler({ room });
  await signaler.connect();

  signaler.onMessage = (msg) => handleSignalMessage(msg);

  logStatus(`Initialized as ${role} in room "${room}"`);

  if (role === "viewer") {
    await startAsViewer();
  } else {
    // Streamer waits for explicit click to start the image stream
    ui.startBtn?.removeAttribute("disabled");
  }
}

// UI wiring
ui.initBtn?.addEventListener("click", () => {
  init().catch(err => {
    console.error(err);
    logStatus(`Init error: ${err.message || err}`);
  });
});

ui.startBtn?.addEventListener("click", () => {
  if (role !== "streamer") return;
  startAsStreamer().catch(err => {
    console.error(err);
    logStatus(`Start error: ${err.message || err}`);
  });
});

// Optional: allow Enter in room input to init
ui.roomInput?.addEventListener("keyup", (e) => {
  if (e.key === "Enter") ui.initBtn?.click();
});
