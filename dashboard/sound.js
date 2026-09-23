// HåkonBench dashboard — synthesized command-console sound effects (Web Audio only, no files).
// Exposes window.SFX = { play(name), muted, setMuted(b), toggle() }.
// Nothing plays until the user has interacted: the AudioContext is created on the first
// pointerdown/keydown, and play() is a no-op before that.
(function () {
  "use strict";
  const KEY = "hb.muted";
  const VOLUME = 0.2;                 // master gain
  const AC = window.AudioContext || window.webkitAudioContext;

  let ctx = null, master = null, noiseBuf = null;
  let armed = false;                  // true after the first user gesture
  let muted = false;
  try { muted = localStorage.getItem(KEY) === "1"; } catch { /* storage blocked */ }

  function ensure() {
    if (!AC) return null;
    if (!ctx) {
      try {
        ctx = new AC();
      } catch { return null; }
      master = ctx.createGain();
      master.gain.value = muted ? 0 : VOLUME;
      const comp = ctx.createDynamicsCompressor();   // keeps stacked sounds from clipping
      comp.threshold.value = -14; comp.ratio.value = 4;
      master.connect(comp).connect(ctx.destination);
      noiseBuf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * 0.5), ctx.sampleRate);
      const d = noiseBuf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    return ctx;
  }

  // First gesture arms the system (and creates the context unless muted).
  function arm() {
    armed = true;
    if (!muted) ensure();
  }
  // click/touchend too: iOS Safari only unlocks audio inside those handlers.
  for (const ev of ["pointerdown", "keydown", "click", "touchend"]) window.addEventListener(ev, arm, true);

  // ── Building blocks ──────────────────────────────────────────
  // Envelope: fast attack, exponential decay to silence at t+dur.
  function env(t, dur, peak, attack = 0.003) {
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(peak, t + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    g.connect(master);
    return g;
  }
  function tone(t, { type = "sine", f0, f1 = f0, dur, peak = 0.5, attack, filter }) {
    const o = ctx.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(f0, t);
    if (f1 !== f0) o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    let out = env(t, dur, peak, attack);
    if (filter) {
      const f = ctx.createBiquadFilter();
      f.type = filter.type; f.frequency.value = filter.freq; f.Q.value = filter.q ?? 0.7;
      f.connect(out); out = f;
    }
    o.connect(out);
    o.start(t); o.stop(t + dur + 0.02);
  }
  function noise(t, { dur, peak = 0.4, type = "bandpass", freq, freq1 = freq, q = 1, attack }) {
    const s = ctx.createBufferSource();
    s.buffer = noiseBuf;
    const f = ctx.createBiquadFilter();
    f.type = type; f.Q.value = q;
    f.frequency.setValueAtTime(freq, t);
    if (freq1 !== freq) f.frequency.exponentialRampToValueAtTime(freq1, t + dur);
    s.connect(f).connect(env(t, dur, peak, attack));
    s.start(t, Math.random() * 0.3); s.stop(t + dur + 0.02);
  }

  // ── Sound set (all 30–250 ms) ────────────────────────────────
  const SOUNDS = {
    // Metallic tick: bright filtered noise snap + a short high ping.
    click(t) {
      noise(t, { dur: 0.03, peak: 0.55, type: "highpass", freq: 3200, q: 0.8, attack: 0.001 });
      tone(t, { type: "square", f0: 2400, f1: 1500, dur: 0.035, peak: 0.12, attack: 0.001, filter: { type: "bandpass", freq: 2200, q: 4 } });
    },
    // Heavy relay thunk: falling low sine body + dull noise knock + contact tick.
    clunk(t) {
      tone(t, { type: "sine", f0: 190, f1: 85, dur: 0.16, peak: 0.95, attack: 0.002 });
      tone(t, { type: "triangle", f0: 380, f1: 170, dur: 0.12, peak: 0.3, attack: 0.001 });
      noise(t, { dur: 0.06, peak: 0.5, type: "lowpass", freq: 900, q: 0.9, attack: 0.001 });
      noise(t + 0.004, { dur: 0.02, peak: 0.3, type: "highpass", freq: 2800, attack: 0.001 });
    },
    // Soft tick: one model in a live job finished.
    tick(t) {
      tone(t, { type: "sine", f0: 1650, f1: 1400, dur: 0.04, peak: 0.15, attack: 0.002 });
      noise(t, { dur: 0.02, peak: 0.08, type: "highpass", freq: 3500, attack: 0.001 });
    },
    // Short low blip: one model in a live job failed.
    blip(t) {
      tone(t, { type: "triangle", f0: 180, f1: 140, dur: 0.07, peak: 0.28, attack: 0.003, filter: { type: "lowpass", freq: 900 } });
    },
    // Console beep: short filtered square.
    beep(t) {
      tone(t, { type: "square", f0: 988, dur: 0.075, peak: 0.28, attack: 0.002, filter: { type: "lowpass", freq: 2600 } });
    },
    // Radar chirp: rising sweep with a faint echo.
    chirp(t) {
      tone(t, { type: "sine", f0: 620, f1: 2300, dur: 0.12, peak: 0.55, attack: 0.004 });
      tone(t, { type: "triangle", f0: 1240, f1: 4200, dur: 0.1, peak: 0.12, attack: 0.004 });
      tone(t + 0.14, { type: "sine", f0: 620, f1: 2300, dur: 0.1, peak: 0.16, attack: 0.004 });
    },
    // Low buzz: two detuned saws beating, lowpassed.
    error(t) {
      const filter = { type: "lowpass", freq: 900, q: 1.2 };
      tone(t, { type: "sawtooth", f0: 104, dur: 0.24, peak: 0.45, attack: 0.006, filter });
      tone(t, { type: "sawtooth", f0: 111, dur: 0.24, peak: 0.4, attack: 0.006, filter });
      tone(t, { type: "square", f0: 55, dur: 0.22, peak: 0.25, attack: 0.006, filter: { type: "lowpass", freq: 400 } });
    },
    // Servo swoosh up (panel slides open).
    open(t) {
      noise(t, { dur: 0.18, peak: 0.45, type: "bandpass", freq: 500, freq1: 3000, q: 2.2, attack: 0.03 });
      tone(t, { type: "sawtooth", f0: 140, f1: 300, dur: 0.16, peak: 0.12, attack: 0.02, filter: { type: "lowpass", freq: 1200 } });
      noise(t + 0.17, { dur: 0.03, peak: 0.25, type: "highpass", freq: 2500, attack: 0.001 });
    },
    // Servo swoosh down (panel closes) ending in a soft latch.
    close(t) {
      noise(t, { dur: 0.15, peak: 0.4, type: "bandpass", freq: 2800, freq1: 450, q: 2.2, attack: 0.02 });
      tone(t, { type: "sawtooth", f0: 300, f1: 130, dur: 0.13, peak: 0.1, attack: 0.015, filter: { type: "lowpass", freq: 1200 } });
      tone(t + 0.13, { type: "sine", f0: 160, f1: 70, dur: 0.06, peak: 0.5, attack: 0.001 });
    },
    // Positive two-tone confirm.
    done(t) {
      const filter = { type: "lowpass", freq: 3500 };
      tone(t, { type: "square", f0: 660, dur: 0.09, peak: 0.22, attack: 0.003, filter });
      tone(t + 0.1, { type: "square", f0: 990, dur: 0.15, peak: 0.24, attack: 0.003, filter });
      tone(t + 0.1, { type: "sine", f0: 1980, dur: 0.12, peak: 0.08, attack: 0.003 });
    },
  };

  // Several cues often fire for one action (a delegated click sound and an explicit hook,
  // e.g. clicking an answer → click + drawer open). They are collected for one tick and
  // only the highest-priority cue plays; on a tie the later (more specific) one wins.
  // Exception: a heavy press that opens a panel plays both — clunk now, the servo 60 ms later.
  const PRIORITY = { click: 0, tick: 1, blip: 1, beep: 1, close: 2, open: 3, clunk: 3, chirp: 4, done: 5, error: 5 };
  let pending = [], timer = 0;
  function flush() {
    timer = 0;
    const cues = pending;
    pending = [];
    if (!cues.length || muted) return;
    const c = ensure();
    if (!c) return;
    let seq;
    if (cues.includes("clunk") && cues.includes("open")) seq = [["clunk", 0], ["open", 0.06]];
    else {
      let best = cues[0];
      for (const n of cues) if (PRIORITY[n] >= PRIORITY[best]) best = n;
      seq = [[best, 0]];
    }
    SFX.last = seq.map(([n]) => n).join("+");   // handy for debugging / tests
    const t0 = c.currentTime + 0.005;
    for (const [n, dt] of seq) {
      try { SOUNDS[n](t0 + dt); } catch { /* never let audio break the UI */ }
    }
  }
  function play(name) {
    if (!armed || muted || !AC || !SOUNDS[name]) return;
    pending.push(name);
    if (!timer) timer = setTimeout(flush, 0);
  }

  // ── Mute ─────────────────────────────────────────────────────
  const btn = document.getElementById("mute-btn");
  function syncButton() {
    if (!btn) return;
    btn.setAttribute("aria-pressed", muted ? "true" : "false");
    btn.title = muted ? "Slå på lyd" : "Slå av lyd";
  }
  function setMuted(b) {
    muted = !!b;
    SFX.muted = muted;
    try { localStorage.setItem(KEY, muted ? "1" : "0"); } catch { /* storage blocked */ }
    if (muted) { pending = []; }
    if (ctx && master) {
      // Ramp rather than jump: also silences anything that is still ringing.
      const now = ctx.currentTime;
      master.gain.cancelScheduledValues(now);
      master.gain.setValueAtTime(master.gain.value, now);
      master.gain.setTargetAtTime(muted ? 0 : VOLUME, now, 0.012);
    }
    syncButton();
  }
  function toggle() {
    setMuted(!muted);
    if (!muted) { armed = true; play("beep"); }
    return muted;
  }
  if (btn) btn.addEventListener("click", toggle);
  syncButton();

  // ── Delegated UI sounds ──────────────────────────────────────
  // First match wins. null = silent here because an explicit hook in app.js plays instead.
  const RULES = [
    ["[data-sfx]", (el) => (el.dataset.sfx === "none" ? null : el.dataset.sfx)],
    ["[data-close-drawer], [data-no]", () => null],
    ["[data-nav]", (el) => (el.dataset.nav === "live" ? "chirp" : "beep")],
    ["[data-tab]", () => "beep"],
    [".btn.primary, .btn.big, .btn.danger", () => "clunk"],
    [".btn, .icon-btn, .link-btn, .model-toggle, .seg button, .toggle-row, .answer-item, .run-card, " +
      ".board tbody tr, .mcard.clickable, .brand, .back, .log summary", () => "click"],
  ];
  document.addEventListener("click", (e) => {
    const t = e.target;
    if (!(t instanceof Element)) return;
    for (const [sel, fn] of RULES) {
      const el = t.closest(sel);
      if (el) {
        if (el.disabled || el.getAttribute("aria-disabled") === "true") return;
        const name = fn(el);
        if (name) play(name);
        return;
      }
    }
  }, true);

  const SFX = { play, muted, setMuted, toggle, last: null };
  window.SFX = SFX;
})();
