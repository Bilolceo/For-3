/* Kino kechasi — sinxron pleyer + WebRTC kameralar. Server: lovebot/web/server.py */
(() => {
  "use strict";
  const tgRaw = window.Telegram && window.Telegram.WebApp;
  const inTelegram = !!(tgRaw && tgRaw.initData); // skript brauzerda ham yuklanadi — initData faqat Telegram ichida bo'ladi
  const tg = inTelegram ? tgRaw : null;
  const $ = (s) => document.querySelector(s);
  const el = {
    app: $("#app"), gate: $("#gate"), gateText: $("#gate-text"), status: $("#status"),
    player: $("#player"), yt: $("#yt"), empty: $("#empty"), hint: $("#hint"), tap: $("#tap"),
    cam: $("#cam"), mic: $("#mic"), sync: $("#sync"), browserLink: $("#browser-link"),
    sourceForm: $("#source-form"), source: $("#source"),
    local: $("#local"), remote: $("#remote"), remoteLabel: $("#remote-label"),
  };

  let session = null, ws = null, me = 0, peer = null, serverOffset = 0;
  let state = null, player = null, currentUrl = "", applyingRemote = 0, reconnectTimer = null;
  let pc = null, localStream = null, makingOffer = false, ignoreOffer = false, polite = false;

  const now = () => (Date.now() + serverOffset) / 1000; // server soatida, soniya
  const hint = (t, warn) => { el.hint.textContent = t || ""; el.hint.classList.toggle("warn", !!warn); };
  const send = (o) => {
    if (o.type !== "signal") console.debug("[kino] send", o.type, o.position !== undefined ? o.position.toFixed(2) : "");
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(o));
  };
  const quiet = (fn) => { applyingRemote++; try { fn(); } finally { setTimeout(() => applyingRemote--, 600); } };

  // ── kirish ───────────────────────────────────────────────────────────
  async function init() {
    if (tg) { tg.ready(); tg.expand(); }
    const params = new URLSearchParams(location.search);
    const body = tg && tg.initData ? { init_data: tg.initData } : { token: params.get("t") || "" };
    let r;
    try {
      r = await fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    } catch (e) { el.gateText.textContent = "Server javob bermadi. Keyinroq urinib ko'r."; return; }
    if (!r.ok) { el.gateText.textContent = "403 — bu yurak band 🔒"; return; }
    session = await r.json();
    me = session.uid;
    const link = `${session.public_url}/app/?t=${session.token}`;
    el.browserLink.href = link;
    if (inTelegram) el.browserLink.onclick = (e) => { e.preventDefault(); tg.openLink(link); };
    else el.browserLink.hidden = true;
    el.gate.hidden = true;
    el.app.hidden = false;
    connect();
    setInterval(driftCheck, 5000);
  }

  // ── WebSocket ────────────────────────────────────────────────────────
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws?t=${session.token}`);
    ws.onopen = () => { setStatus(); };
    ws.onclose = () => { setStatus("ulanish uzildi, qayta ulanmoqda…"); clearTimeout(reconnectTimer); reconnectTimer = setTimeout(connect, 2000); };
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.server_time) serverOffset = m.server_time * 1000 - Date.now();
      if (m.type === "state") console.debug("[kino] state", m.event, "by", m.by, "playing", m.state.playing, "pos", m.state.position.toFixed(2));
      switch (m.type) {
        case "hello":
          peer = m.peers.length ? m.peers[0] : null;
          polite = peer ? me > peer.uid : false;
          setStatus();
          if (m.state && m.state.url) applyState(m.state);
          if (peer && localStream) ensurePC();
          break;
        case "peer_joined":
          peer = { uid: m.uid, name: m.name };
          polite = me > peer.uid;
          setStatus();
          if (localStream) ensurePC();
          break;
        case "peer_left":
          peer = null; setStatus(); teardownPC();
          break;
        case "state":
          // o'zim yuborgan play/pause/seek allaqachon lokal bajarilgan; manba esa hamma uchun yuklanadi
          if (m.by !== me || m.event === "source") applyState(m.state, m.event);
          else state = m.state;
          break;
        case "signal":
          handleSignal(m.data);
          break;
      }
    };
  }

  function setStatus(text) {
    if (text) { el.status.textContent = text; el.status.classList.remove("on"); return; }
    if (peer) { el.status.textContent = `${peer.name} xonada`; el.status.classList.add("on"); el.remoteLabel.textContent = peer.name; }
    else { el.status.textContent = "ikkinchi tomon hali kirmadi"; el.status.classList.remove("on"); el.remoteLabel.textContent = "—"; }
  }

  // ── pleyer adapterlari ───────────────────────────────────────────────
  function filePlayer(url) {
    const v = el.player;
    el.yt.hidden = true; v.hidden = false;
    if (v._hls) { v._hls.destroy(); v._hls = null; }
    if (/\.m3u8(\?|$)/i.test(url) && window.Hls && Hls.isSupported()) {
      const h = new Hls(); h.loadSource(url); h.attachMedia(v); v._hls = h;
    } else {
      v.src = url;
    }
    v.onerror = () => hint("Video ochilmadi — havola to'g'ridan-to'g'ri .mp4/.m3u8 faylga olib borishi kerak.", true);
    v.onplay = () => { if (!applyingRemote) send({ type: "play", position: v.currentTime }); };
    v.onpause = () => { if (!applyingRemote && !v.seeking) send({ type: "pause", position: v.currentTime }); };
    v.onseeked = () => { if (!applyingRemote) send({ type: "seek", position: v.currentTime }); };
    return {
      kind: "file",
      time: () => v.currentTime || 0,
      seek: (t) => { v.currentTime = t; },
      play: () => v.play().catch(() => { el.tap.hidden = false; }),
      pause: () => v.pause(),
      paused: () => v.paused,
      ready: (cb) => (v.readyState >= 1 ? cb() : v.addEventListener("loadedmetadata", cb, { once: true })),
    };
  }

  let ytApiPromise = null;
  function loadYTApi() {
    if (window.YT && window.YT.Player) return Promise.resolve();
    if (!ytApiPromise) ytApiPromise = new Promise((res) => {
      window.onYouTubeIframeAPIReady = res;
      const s = document.createElement("script"); s.src = "https://www.youtube.com/iframe_api"; document.head.appendChild(s);
    });
    return ytApiPromise;
  }
  function youtubeId(url) {
    const m = url.match(/(?:v=|youtu\.be\/|shorts\/|embed\/)([A-Za-z0-9_-]{11})/);
    return m ? m[1] : null;
  }
  function youtubePlayer(url) {
    el.player.hidden = true; el.player.pause(); el.player.removeAttribute("src");
    el.yt.hidden = false; el.yt.innerHTML = '<div id="yt-inner"></div>';
    let yt = null, readyCbs = [], lastT = 0, lastWall = 0;
    const api = {
      kind: "youtube",
      time: () => (yt && yt.getCurrentTime ? yt.getCurrentTime() : 0),
      seek: (t) => yt && yt.seekTo(t, true),
      play: () => yt && yt.playVideo(),
      pause: () => yt && yt.pauseVideo(),
      paused: () => !yt || yt.getPlayerState() !== 1,
      ready: (cb) => (yt ? cb() : readyCbs.push(cb)),
      _poll: null,
    };
    loadYTApi().then(() => {
      yt = new YT.Player("yt-inner", {
        videoId: youtubeId(url), playerVars: { playsinline: 1, controls: 1, rel: 0, modestbranding: 1 },
        events: {
          onReady: () => { readyCbs.forEach((cb) => cb()); readyCbs = []; lastT = api.time(); lastWall = Date.now(); },
          onStateChange: (e) => {
            if (applyingRemote) return;
            if (e.data === 1) send({ type: "play", position: api.time() });
            else if (e.data === 2) send({ type: "pause", position: api.time() });
          },
        },
      });
      // seek aniqlash: vaqt sakrasa — seek
      api._poll = setInterval(() => {
        if (!yt || !yt.getCurrentTime) return;
        const t = api.time(), wall = Date.now();
        const expected = api.paused() ? lastT : lastT + (wall - lastWall) / 1000;
        if (Math.abs(t - expected) > 1.5 && !applyingRemote) send({ type: "seek", position: t });
        lastT = t; lastWall = wall;
      }, 500);
    });
    return api;
  }

  function loadSource(url, kind) {
    if (player && player._poll) clearInterval(player._poll);
    player = kind === "youtube" ? youtubePlayer(url) : filePlayer(url);
    currentUrl = url;
    el.empty.hidden = true;
    el.source.value = url;
    hint("");
  }

  // ── sinxronlash ──────────────────────────────────────────────────────
  function applyState(s, event) {
    state = s;
    if (!s.url) return;
    const switching = !player || currentUrl !== s.url;
    if (switching) loadSource(s.url, s.kind);
    player.ready(() => {
      const expected = s.playing ? s.position + (now() - s.updated_at) : s.position;
      quiet(() => {
        if (switching || event === "seek" || Math.abs(player.time() - expected) > 1.0) player.seek(Math.max(0, expected));
        if (s.playing) player.play(); else player.pause();
      });
    });
  }
  function driftCheck() {
    if (!state || !state.playing || !player || applyingRemote) return;
    const expected = state.position + (now() - state.updated_at);
    if (Math.abs(player.time() - expected) > 2.0) quiet(() => player.seek(expected));
  }
  el.tap.onclick = () => {
    // Brauzer avtomatik ijroni bloklagan — foydalanuvchi bosgach hozirgi holatga sinxron ulanadi
    el.tap.hidden = true;
    if (state) applyState(state);
  };
  el.sync.onclick = () => {
    if (!player) return;
    send({ type: player.paused() ? "pause" : "play", position: player.time() });
    hint("Holating ikkinchi tomonga yuborildi");
  };
  el.sourceForm.onsubmit = (e) => {
    e.preventDefault();
    const url = el.source.value.trim();
    if (!/^https?:\/\//.test(url)) { hint("Havola https:// bilan boshlansin", true); return; }
    if (/youtu/.test(url) && !youtubeId(url)) { hint("YouTube havolasi tushunarsiz", true); return; }
    send({ type: "source", url });
    hint("");
  };

  // ── kamera / WebRTC (perfect negotiation) ────────────────────────────
  el.cam.onclick = async () => {
    if (localStream) { stopCamera(); return; }
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 } }, audio: true });
    } catch (e) {
      hint(inTelegram ? "Telegram ichida kamera ochilmadi — 🌐 Brauzerda och (kompyuterda eng yaxshi)." : "Kameraga ruxsat berilmadi.", true);
      return;
    }
    el.local.srcObject = localStream; el.local.parentElement.classList.remove("off");
    el.cam.classList.add("on"); el.mic.disabled = false; el.mic.classList.add("on");
    if (peer) ensurePC();
  };
  el.mic.onclick = () => {
    if (!localStream) return;
    const track = localStream.getAudioTracks()[0]; if (!track) return;
    track.enabled = !track.enabled; el.mic.classList.toggle("on", track.enabled);
  };
  function stopCamera() {
    if (localStream) localStream.getTracks().forEach((t) => t.stop());
    localStream = null; el.local.srcObject = null; el.local.parentElement.classList.add("off");
    el.cam.classList.remove("on"); el.mic.disabled = true; el.mic.classList.remove("on");
    teardownPC();
  }
  function ensurePC() {
    if (!pc) {
      pc = new RTCPeerConnection({ iceServers: session.ice_servers });
      pc.ontrack = (e) => { el.remote.srcObject = e.streams[0]; el.remote.parentElement.classList.remove("off"); };
      pc.onicecandidate = (e) => { if (e.candidate) send({ type: "signal", data: { candidate: e.candidate } }); };
      pc.onnegotiationneeded = async () => {
        try { makingOffer = true; await pc.setLocalDescription(); send({ type: "signal", data: { description: pc.localDescription } }); }
        catch (err) { console.error(err); } finally { makingOffer = false; }
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "failed") { hint("Video ulanishi o'tmadi — internetni tekshir yoki qayta ulan.", true); }
        if (pc.connectionState === "connected") hint("");
      };
    }
    if (localStream) {
      const have = new Set(pc.getSenders().map((s) => s.track));
      localStream.getTracks().forEach((t) => { if (!have.has(t)) pc.addTrack(t, localStream); });
    }
  }
  async function handleSignal(data) {
    if (!data) return;
    ensurePC();
    try {
      if (data.description) {
        const offerCollision = data.description.type === "offer" && (makingOffer || pc.signalingState !== "stable");
        ignoreOffer = !polite && offerCollision;
        if (ignoreOffer) return;
        await pc.setRemoteDescription(data.description);
        if (data.description.type === "offer") {
          await pc.setLocalDescription();
          send({ type: "signal", data: { description: pc.localDescription } });
        }
      } else if (data.candidate) {
        try { await pc.addIceCandidate(data.candidate); } catch (err) { if (!ignoreOffer) throw err; }
      }
    } catch (err) { console.error("signal", err); }
  }
  function teardownPC() {
    if (pc) { pc.close(); pc = null; }
    el.remote.srcObject = null; el.remote.parentElement.classList.add("off");
  }

  el.local.parentElement.classList.add("off");
  el.remote.parentElement.classList.add("off");
  init();
})();
