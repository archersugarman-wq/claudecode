'use strict';
/**
 * Procedural "video" renderer. Seed content in this demo has no real video
 * files (there's no video corpus to source), so each seed post instead
 * renders a deterministic, looping generative animation on <canvas> --
 * styled per creator niche -- with the caption/sound/UI chrome overlaid
 * exactly like a real clip. Real uploads (via file picker or webcam
 * recording) play through an actual <video> element instead; see
 * views/feed.js for the switch between the two.
 */

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const PALETTES = {
  plasma: ['#ff5f6d', '#ffc371', '#ff2e63', '#ff9a3c'],
  matrix: ['#00ff87', '#00b359', '#003d1a'],
  aurora: ['#00c9ff', '#92fe9d', '#7b2ff7', '#00ffa3'],
  waves: ['#4facfe', '#00f2fe', '#0b3d91'],
  particles: ['#a18cd1', '#fbc2eb', '#8ec5fc'],
  bounce: ['#ff6a88', '#ff99ac', '#ffb199'],
  bars: ['#f857a6', '#ff5858', '#ffd26f'],
  confetti: ['#ff9a9e', '#fecfef', '#fbc2eb', '#a18cd1', '#fad0c4'],
  starfield: ['#0f2027', '#2c5364', '#e0f7fa'],
  tunnel: ['#12c2e9', '#c471ed', '#f64f59'],
};

function hueShift(hex, degrees) {
  // quick hex -> HSL-ish shift by re-deriving via canvas is overkill; just
  // return the original color mixed toward white/black slightly per seed
  // using simple RGB rotation for cheap per-video variety.
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const rot = ((degrees % 3) + 3) % 3;
  if (rot === 1) [r, g, b] = [g, b, r];
  if (rot === 2) [r, g, b] = [b, r, g];
  return `rgb(${r},${g},${b})`;
}

function setupCanvas(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  function resize() {
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(1, Math.round(rect.width * dpr));
    const h = Math.max(1, Math.round(rect.height * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
  }
  resize();
  return { dpr, resize };
}

// --- individual style renderers --------------------------------------
// Each returns a draw(ctx, w, h, t, rnd, palette, state) function. `state`
// is a plain object persisted across frames for this canvas instance,
// seeded once in init().

const STYLES = {
  plasma(rnd, palette) {
    const blobs = new Array(4).fill(0).map((_, i) => ({
      cx: 0.2 + rnd() * 0.6, cy: 0.2 + rnd() * 0.6,
      rx: 0.35 + rnd() * 0.25, ry: 0.35 + rnd() * 0.25,
      speed: 0.15 + rnd() * 0.25, phase: rnd() * Math.PI * 2,
      color: palette[i % palette.length],
    }));
    return (ctx, w, h, t) => {
      ctx.fillStyle = '#0a0a0f';
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      blobs.forEach((b) => {
        const x = (b.cx + Math.sin(t * b.speed + b.phase) * 0.18) * w;
        const y = (b.cy + Math.cos(t * b.speed * 0.8 + b.phase) * 0.18) * h;
        const r = Math.max(w, h) * (b.rx + b.ry) * 0.5;
        const grad = ctx.createRadialGradient(x, y, 0, x, y, r);
        grad.addColorStop(0, b.color);
        grad.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalCompositeOperation = 'source-over';
    };
  },

  matrix(rnd, palette) {
    const cols = 28;
    const drops = new Array(cols).fill(0).map(() => rnd());
    const speeds = new Array(cols).fill(0).map(() => 0.3 + rnd() * 0.6);
    const chars = '01アイウエオカキクケコサシスセソ';
    return (ctx, w, h, t, dt) => {
      ctx.fillStyle = 'rgba(4,10,6,0.28)';
      ctx.fillRect(0, 0, w, h);
      const fontSize = Math.max(12, w / cols);
      ctx.font = `${fontSize}px monospace`;
      for (let i = 0; i < cols; i++) {
        drops[i] += speeds[i] * dt * 0.6;
        const y = (drops[i] % 1.2) * h * 1.2 - h * 0.2;
        const x = i * (w / cols) + fontSize * 0.2;
        ctx.fillStyle = palette[0];
        ctx.fillText(chars[(i + Math.floor(t * 4)) % chars.length], x, y);
        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.fillText(chars[(i * 3 + Math.floor(t * 6)) % chars.length], x, y - fontSize);
      }
    };
  },

  aurora(rnd, palette) {
    const bands = new Array(3).fill(0).map((_, i) => ({
      offset: rnd() * Math.PI * 2, amp: 0.08 + rnd() * 0.08,
      color: palette[i % palette.length], speed: 0.2 + rnd() * 0.2,
    }));
    return (ctx, w, h, t) => {
      const sky = ctx.createLinearGradient(0, 0, 0, h);
      sky.addColorStop(0, '#02040a');
      sky.addColorStop(1, '#0a1128');
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      bands.forEach((band, bi) => {
        ctx.beginPath();
        ctx.moveTo(0, h);
        for (let x = 0; x <= w; x += w / 40) {
          const y = h * (0.35 + bi * 0.12) +
            Math.sin(x * 0.01 + t * band.speed + band.offset) * h * band.amp;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(w, h);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, h * 0.2, 0, h);
        grad.addColorStop(0, band.color);
        grad.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.globalAlpha = 0.5;
        ctx.fillStyle = grad;
        ctx.fill();
      });
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
    };
  },

  waves(rnd, palette) {
    const lines = new Array(4).fill(0).map((_, i) => ({
      phase: rnd() * Math.PI * 2, freq: 1.5 + rnd() * 1.5, color: palette[i % palette.length],
    }));
    return (ctx, w, h, t) => {
      ctx.fillStyle = '#05070d';
      ctx.fillRect(0, 0, w, h);
      lines.forEach((line, i) => {
        ctx.beginPath();
        for (let x = 0; x <= w; x += w / 60) {
          const y = h / 2 + Math.sin((x / w) * Math.PI * line.freq + t * 1.4 + line.phase) * h * (0.12 + i * 0.03);
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = line.color;
        ctx.globalAlpha = 0.55;
        ctx.lineWidth = Math.max(2, w * 0.006);
        ctx.stroke();
      });
      ctx.globalAlpha = 1;
    };
  },

  particles(rnd, palette) {
    const N = 45;
    const pts = new Array(N).fill(0).map(() => ({
      x: rnd(), y: rnd(), vx: (rnd() - 0.5) * 0.05, vy: (rnd() - 0.5) * 0.05,
    }));
    return (ctx, w, h, t, dt) => {
      ctx.fillStyle = '#080814';
      ctx.fillRect(0, 0, w, h);
      pts.forEach((p) => {
        p.x += p.vx * dt; p.y += p.vy * dt;
        if (p.x < 0) p.x += 1; if (p.x > 1) p.x -= 1;
        if (p.y < 0) p.y += 1; if (p.y > 1) p.y -= 1;
      });
      const maxDist = Math.min(w, h) * 0.16;
      ctx.strokeStyle = palette[2];
      for (let i = 0; i < N; i++) {
        for (let j = i + 1; j < N; j++) {
          const dx = (pts[i].x - pts[j].x) * w, dy = (pts[i].y - pts[j].y) * h;
          const dist = Math.hypot(dx, dy);
          if (dist < maxDist) {
            ctx.globalAlpha = (1 - dist / maxDist) * 0.35;
            ctx.beginPath();
            ctx.moveTo(pts[i].x * w, pts[i].y * h);
            ctx.lineTo(pts[j].x * w, pts[j].y * h);
            ctx.stroke();
          }
        }
      }
      ctx.globalAlpha = 1;
      pts.forEach((p, i) => {
        ctx.fillStyle = palette[i % palette.length];
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, Math.max(2, w * 0.006), 0, Math.PI * 2);
        ctx.fill();
      });
    };
  },

  bounce(rnd, palette) {
    const balls = new Array(3).fill(0).map((_, i) => ({
      x: rnd(), y: rnd(), vx: (rnd() - 0.5) * 0.35, vy: (rnd() - 0.5) * 0.35,
      r: 0.09 + rnd() * 0.06, color: palette[i % palette.length],
    }));
    return (ctx, w, h, t, dt) => {
      ctx.fillStyle = 'rgba(10,8,14,0.35)';
      ctx.fillRect(0, 0, w, h);
      balls.forEach((b) => {
        b.x += b.vx * dt * 0.5; b.y += b.vy * dt * 0.5;
        if (b.x - b.r < 0 || b.x + b.r > 1) b.vx *= -1;
        if (b.y - b.r < 0 || b.y + b.r > 1) b.vy *= -1;
        b.x = Math.min(1 - b.r, Math.max(b.r, b.x));
        b.y = Math.min(1 - b.r, Math.max(b.r, b.y));
        const grad = ctx.createRadialGradient(b.x * w, b.y * h, 0, b.x * w, b.y * h, b.r * w);
        grad.addColorStop(0, b.color);
        grad.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(b.x * w, b.y * h, b.r * w, 0, Math.PI * 2);
        ctx.fill();
      });
    };
  },

  bars(rnd, palette) {
    const N = 24;
    const bars = new Array(N).fill(0).map(() => ({ phase: rnd() * Math.PI * 2, speed: 2 + rnd() * 3 }));
    return (ctx, w, h, t) => {
      ctx.fillStyle = '#0c0510';
      ctx.fillRect(0, 0, w, h);
      const bw = w / N;
      bars.forEach((b, i) => {
        const amp = (Math.sin(t * b.speed + b.phase) * 0.5 + 0.5) * 0.4 + 0.06;
        const barH = amp * h;
        const grad = ctx.createLinearGradient(0, h / 2 - barH / 2, 0, h / 2 + barH / 2);
        grad.addColorStop(0, palette[i % palette.length]);
        grad.addColorStop(1, palette[(i + 1) % palette.length]);
        ctx.fillStyle = grad;
        const x = i * bw + bw * 0.15;
        ctx.fillRect(x, h / 2 - barH / 2, bw * 0.7, barH);
      });
    };
  },

  confetti(rnd, palette) {
    const N = 60;
    const bits = new Array(N).fill(0).map(() => ({
      x: rnd(), y: rnd() * -1, vy: 0.15 + rnd() * 0.25, vx: (rnd() - 0.5) * 0.05,
      rot: rnd() * Math.PI, vr: (rnd() - 0.5) * 4, size: 0.012 + rnd() * 0.018,
      color: palette[Math.floor(rnd() * palette.length)],
    }));
    return (ctx, w, h, t, dt) => {
      ctx.fillStyle = '#0e0a16';
      ctx.fillRect(0, 0, w, h);
      bits.forEach((c) => {
        c.y += c.vy * dt * 0.4; c.x += c.vx * dt * 0.4; c.rot += c.vr * dt * 0.2;
        if (c.y > 1.1) { c.y = -0.1; c.x = rnd(); }
        ctx.save();
        ctx.translate(c.x * w, c.y * h);
        ctx.rotate(c.rot);
        ctx.fillStyle = c.color;
        const s = c.size * w;
        ctx.fillRect(-s / 2, -s / 3, s, s * 0.66);
        ctx.restore();
      });
    };
  },

  starfield(rnd, palette) {
    const N = 90;
    const stars = new Array(N).fill(0).map(() => ({ x: rnd() * 2 - 1, y: rnd() * 2 - 1, z: rnd() }));
    return (ctx, w, h, t, dt) => {
      ctx.fillStyle = '#000308';
      ctx.fillRect(0, 0, w, h);
      const cx = w / 2, cy = h / 2;
      stars.forEach((s) => {
        s.z -= dt * 0.18;
        if (s.z <= 0.02) { s.z = 1; s.x = rnd() * 2 - 1; s.y = rnd() * 2 - 1; }
        const k = 0.5 / s.z;
        const x = cx + s.x * k * cx;
        const y = cy + s.y * k * cy;
        if (x < 0 || x > w || y < 0 || y > h) return;
        const size = (1 - s.z) * 3 + 0.5;
        ctx.fillStyle = palette[2];
        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fill();
      });
    };
  },

  tunnel(rnd, palette) {
    const rings = 14;
    const twist = rnd() * Math.PI;
    return (ctx, w, h, t) => {
      ctx.fillStyle = '#050212';
      ctx.fillRect(0, 0, w, h);
      const cx = w / 2, cy = h / 2;
      const maxR = Math.hypot(cx, cy);
      for (let i = rings; i >= 0; i--) {
        const depth = ((i / rings) + (t * 0.25 % 1)) % 1;
        const r = depth * maxR;
        const sides = 6;
        ctx.beginPath();
        for (let s = 0; s <= sides; s++) {
          const ang = (s / sides) * Math.PI * 2 + twist + t * 0.3;
          const x = cx + Math.cos(ang) * r;
          const y = cy + Math.sin(ang) * r;
          if (s === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = palette[i % palette.length];
        ctx.globalAlpha = 0.15 + (1 - depth) * 0.5;
        ctx.lineWidth = Math.max(1.5, w * 0.004);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    };
  },
};

/**
 * @param {HTMLCanvasElement} canvas
 * @param {string} style one of the STYLES keys (falls back to 'plasma')
 * @param {number} seed integer seed for deterministic layout
 */
function createProceduralVideo(canvas, style, seed) {
  const ctx = canvas.getContext('2d', { alpha: false });
  const rnd = mulberry32((seed || 0) + 1);
  const paletteBase = PALETTES[style] || PALETTES.plasma;
  const palette = paletteBase.map((c, i) => hueShift(c, (seed + i) % 3));
  const factory = STYLES[style] || STYLES.plasma;
  const draw = factory(rnd, palette);
  const { resize } = setupCanvas(canvas);

  let raf = null;
  let last = performance.now();
  let elapsed = (seed % 17) * 0.6; // desync loops between simultaneously-visible clips

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    elapsed += dt;
    resize();
    draw(ctx, canvas.width, canvas.height, elapsed, dt);
    raf = requestAnimationFrame(frame);
  }

  return {
    start() {
      if (raf) return;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    },
    stop() {
      if (raf) cancelAnimationFrame(raf);
      raf = null;
    },
    destroy() {
      this.stop();
    },
  };
}

window.createProceduralVideo = createProceduralVideo;
