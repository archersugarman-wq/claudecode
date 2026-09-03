'use strict';

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/** Turn "check this out #cool #fyp" into caption HTML with clickable hashtags. */
function renderCaption(caption) {
  const escaped = escapeHtml(caption);
  return escaped.replace(/#([a-z0-9_]+)/gi, (m, tag) => `<a href="#/tag/${tag.toLowerCase()}" class="tag-link" data-nav>#${tag}</a>`);
}

function formatCount(n) {
  n = Number(n) || 0;
  if (n < 1000) return String(n);
  if (n < 1_000_000) {
    const v = n / 1000;
    return (v >= 100 ? v.toFixed(0) : v.toFixed(1).replace(/\.0$/, '')) + 'K';
  }
  if (n < 1_000_000_000) {
    const v = n / 1_000_000;
    return (v >= 100 ? v.toFixed(0) : v.toFixed(1).replace(/\.0$/, '')) + 'M';
  }
  const v = n / 1_000_000_000;
  return v.toFixed(1).replace(/\.0$/, '') + 'B';
}

function timeAgo(ts) {
  const s = Math.max(0, (Date.now() - ts) / 1000);
  if (s < 60) return 'now';
  const m = s / 60;
  if (m < 60) return `${Math.floor(m)}m ago`;
  const h = m / 60;
  if (h < 24) return `${Math.floor(h)}h ago`;
  const d = h / 24;
  if (d < 7) return `${Math.floor(d)}d ago`;
  const w = d / 7;
  if (w < 5) return `${Math.floor(w)}w ago`;
  const dt = new Date(ts);
  return dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: dt.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
}

const AVATAR_PALETTES = [
  ['#ff5f6d', '#ffc371'], ['#4facfe', '#00f2fe'], ['#a18cd1', '#fbc2eb'], ['#ff9a9e', '#fecfef'],
  ['#00c9ff', '#92fe9d'], ['#f857a6', '#ff5858'], ['#12c2e9', '#c471ed'], ['#ff6a88', '#ff99ac'],
  ['#0f2027', '#2c5364'], ['#f6d365', '#fda085'], ['#84fab0', '#8fd3f4'], ['#a1c4fd', '#c2e9fb'],
  ['#fccb90', '#d57eeb'], ['#e0c3fc', '#8ec5fc'],
];

function avatarSvg(seed, displayName, size = 40) {
  const palette = AVATAR_PALETTES[(Math.abs(seed || 0) - 1 + AVATAR_PALETTES.length) % AVATAR_PALETTES.length] || AVATAR_PALETTES[0];
  const initial = (displayName || '?').trim().charAt(0).toUpperCase() || '?';
  const gradId = `av${seed}-${Math.random().toString(36).slice(2, 7)}`;
  return `<svg width="${size}" height="${size}" viewBox="0 0 40 40" role="img" aria-label="${escapeHtml(displayName)}">
    <defs><linearGradient id="${gradId}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${palette[0]}"/><stop offset="1" stop-color="${palette[1]}"/>
    </linearGradient></defs>
    <circle cx="20" cy="20" r="20" fill="url(#${gradId})"/>
    <text x="20" y="27" text-anchor="middle" font-size="18" font-family="inherit" fill="rgba(255,255,255,.95)" font-weight="700">${escapeHtml(initial)}</text>
  </svg>`;
}

function debounce(fn, ms) {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

function el(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function toast(message) {
  let host = document.getElementById('toast-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'toast-host';
    document.body.appendChild(host);
  }
  const node = el(`<div class="toast">${escapeHtml(message)}</div>`);
  host.appendChild(node);
  requestAnimationFrame(() => node.classList.add('show'));
  setTimeout(() => {
    node.classList.remove('show');
    setTimeout(() => node.remove(), 250);
  }, 2600);
}

window.Helpers = { escapeHtml, renderCaption, formatCount, timeAgo, avatarSvg, debounce, el, toast };
