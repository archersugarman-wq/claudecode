'use strict';
/* Shell: global state, hash router, nav rendering, modal host. */

const Store = {
  currentUser: null,
  unreadNotifications: 0,
  afterLoginRedirect: null,
  listeners: [],
  onChange(fn) { this.listeners.push(fn); },
  emit() { this.listeners.forEach((fn) => { try { fn(); } catch (e) { console.error(e); } }); },
  async refreshMe() {
    try {
      const { user } = await Api.me();
      this.currentUser = user;
    } catch (e) {
      this.currentUser = null;
    }
    this.emit();
    return this.currentUser;
  },
  async refreshUnread() {
    if (!this.currentUser) { this.unreadNotifications = 0; this.emit(); return; }
    try {
      const { unread } = await Api.notifications();
      this.unreadNotifications = unread;
    } catch (e) { /* ignore */ }
    this.emit();
  },
  setUser(user) {
    this.currentUser = user;
    this.emit();
  },
};
window.Store = Store;

// ---------------------------------------------------------------------
// Modal host (used by comments drawer, share sheet, confirm dialogs, ...)
// ---------------------------------------------------------------------
const Modal = {
  current: null,
  _esc: null,
  onCloseCb: null,
  open(contentEl, opts = {}) {
    this.close();
    const backdrop = Helpers.el(`<div class="modal-backdrop"></div>`);
    backdrop.appendChild(contentEl);
    document.getElementById('modal-root').appendChild(backdrop);
    requestAnimationFrame(() => backdrop.classList.add('show'));
    backdrop.addEventListener('mousedown', (e) => {
      if (e.target === backdrop && opts.dismissible !== false) this.close();
    });
    this._esc = (e) => { if (e.key === 'Escape' && opts.dismissible !== false) this.close(); };
    document.addEventListener('keydown', this._esc);
    this.current = backdrop;
    this.onCloseCb = opts.onClose || null;
    return backdrop;
  },
  close() {
    if (this.current) {
      const node = this.current;
      node.classList.remove('show');
      setTimeout(() => node.remove(), 200);
      this.current = null;
    }
    if (this._esc) { document.removeEventListener('keydown', this._esc); this._esc = null; }
    if (this.onCloseCb) { const cb = this.onCloseCb; this.onCloseCb = null; cb(); }
  },
};
window.Modal = Modal;

// ---------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------
const ROUTES = [
  { re: /^\/$/, view: 'feed', guard: false, params: () => ({ tab: 'foryou' }) },
  { re: /^\/following\/?$/, view: 'feed', guard: false, params: () => ({ tab: 'following' }) },
  { re: /^\/video\/([^/]+)\/?$/, view: 'feed', guard: false, params: (m) => ({ tab: 'foryou', focusId: m[1] }) },
  { re: /^\/upload\/?$/, view: 'upload', guard: true, params: () => ({}) },
  { re: /^\/search\/?$/, view: 'search', guard: false, params: () => ({}) },
  { re: /^\/tag\/([^/]+)\/?$/, view: 'tag', guard: false, params: (m) => ({ tag: decodeURIComponent(m[1]) }) },
  { re: /^\/sound\/([^/]+)\/?$/, view: 'sound', guard: false, params: (m) => ({ id: m[1] }) },
  { re: /^\/notifications\/?$/, view: 'notifications', guard: true, params: () => ({}) },
  { re: /^\/login\/?$/, view: 'auth', guard: false, params: () => ({}) },
  { re: /^\/settings\/?$/, view: 'settings', guard: true, params: () => ({}) },
  { re: /^\/user\/([^/]+)\/liked\/?$/, view: 'profile', guard: false, params: (m) => ({ username: m[1], tab: 'liked' }) },
  { re: /^\/user\/([^/]+)\/?$/, view: 'profile', guard: false, params: (m) => ({ username: m[1], tab: 'videos' }) },
];

let mounted = null; // { name, unmount() }

function parseHash() {
  const raw = (location.hash || '#/').slice(1);
  const [pathPart, queryPart] = raw.split('?');
  return { path: pathPart || '/', query: Object.fromEntries(new URLSearchParams(queryPart || '')) };
}

function navigate(hash) {
  if (location.hash === hash) { route(); } else { location.hash = hash; }
}
window.navigate = navigate;

async function route() {
  const { path, query } = parseHash();
  const match = ROUTES.find((r) => r.re.test(path));
  const viewName = match ? match.view : '404';
  const params = match ? match.params(match.re.exec(path)) : {};

  if (match && match.guard && !Store.currentUser) {
    Store.afterLoginRedirect = `#${path}${Object.keys(query).length ? '?' + new URLSearchParams(query).toString() : ''}`;
    if (location.hash !== '#/login') { location.hash = '#/login'; return; }
  }

  const root = document.getElementById('view-root');
  if (mounted && typeof mounted.unmount === 'function') {
    try { mounted.unmount(); } catch (e) { console.error('unmount error', e); }
  }
  mounted = null;
  root.innerHTML = '';
  root.className = '';
  root.scrollTop = 0;

  const view = (window.Views && window.Views[viewName]) || notFoundView;
  try {
    const instance = await view.mount(root, params, query);
    mounted = instance || { unmount() {} };
  } catch (e) {
    console.error('mount error', e);
    root.innerHTML = `<div class="empty-state"><p>Something went wrong loading this page.</p></div>`;
  }
  renderNav();
  root.focus({ preventScroll: true });
}

const notFoundView = {
  mount(root) {
    root.innerHTML = `<div class="empty-state">
      <h2>Page not found</h2>
      <p>That page doesn't exist.</p>
      <a href="#/" class="btn btn-primary" data-nav>Go home</a>
    </div>`;
    return { unmount() {} };
  },
};

// ---------------------------------------------------------------------
// Nav (sidebar + bottom tabs)
// ---------------------------------------------------------------------
function navItems() {
  const authed = !!Store.currentUser;
  const profileHref = authed ? `#/user/${Store.currentUser.username}` : '#/login';
  return [
    { href: '#/', icon: 'home', label: 'For You', match: /^#\/?$/ },
    { href: '#/following', icon: 'users', label: 'Following', match: /^#\/following/ },
    { href: '#/upload', icon: 'plus', label: 'Upload', match: /^#\/upload/, primary: true },
    { href: '#/notifications', icon: 'inbox', label: 'Inbox', match: /^#\/notifications/, badge: authed },
    { href: profileHref, icon: 'user', label: authed ? 'Profile' : 'Log in', match: /^#\/user\// },
  ];
}

function renderNav() {
  const items = navItems();
  const hash = location.hash || '#/';

  const sidebarSearch = `
    <form class="sidebar-search" id="sidebar-search-form">
      <span class="sidebar-search-icon">${icon('search', 18)}</span>
      <input id="sidebar-search-input" type="search" placeholder="Search" autocomplete="off">
    </form>`;

  const sidebarLinks = items.map((it) => `
    <a href="${it.href}" data-nav class="nav-item ${it.match.test(hash) ? 'active' : ''} ${it.primary ? 'nav-primary' : ''}">
      <span class="nav-icon">${icon(it.icon, 24)}${it.badge && Store.unreadNotifications ? `<span class="nav-dot"></span>` : ''}</span>
      <span class="nav-label">${Helpers.escapeHtml(it.label)}</span>
    </a>`).join('');

  const authFooter = Store.currentUser
    ? `<button class="nav-item nav-logout" id="nav-logout-btn"><span class="nav-icon">${icon('logout', 22)}</span><span class="nav-label">Log out</span></button>`
    : '';

  document.getElementById('sidebar').innerHTML = `
    ${sidebarSearch}
    <div class="nav-list">${sidebarLinks}</div>
    <div class="nav-footer">${authFooter}<p class="nav-copyright">TikTok Clone &middot; demo build</p></div>
  `;

  document.getElementById('bottom-tabs').innerHTML = items.map((it) => `
    <a href="${it.href}" data-nav class="tab-item ${it.match.test(hash) ? 'active' : ''} ${it.primary ? 'tab-primary' : ''}">
      <span class="nav-icon">${icon(it.icon, it.primary ? 28 : 24)}${it.badge && Store.unreadNotifications ? `<span class="nav-dot"></span>` : ''}</span>
      ${!it.primary ? `<span class="tab-label">${Helpers.escapeHtml(it.label)}</span>` : ''}
    </a>`).join('');

  const logoutBtn = document.getElementById('nav-logout-btn');
  if (logoutBtn) logoutBtn.addEventListener('click', doLogout);

  const sidebarForm = document.getElementById('sidebar-search-form');
  sidebarForm.addEventListener('submit', onSearchSubmit);
}

async function doLogout() {
  try { await Api.logout(); } catch (e) { /* ignore */ }
  Store.setUser(null);
  Helpers.toast('Logged out');
  navigate('#/');
}

function onSearchSubmit(e) {
  e.preventDefault();
  const input = e.currentTarget.querySelector('input[type="search"]');
  const q = (input.value || '').trim();
  navigate(`#/search${q ? '?q=' + encodeURIComponent(q) : ''}`);
}

// ---------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------
async function boot() {
  document.getElementById('topbar-search-btn').innerHTML = icon('search', 20);
  document.getElementById('topbar-upload-btn').innerHTML = icon('plus', 22);
  document.getElementById('topbar-search-form').addEventListener('submit', onSearchSubmit);

  Store.onChange(renderNav);

  await Store.refreshMe();
  renderNav();
  await Store.refreshUnread();

  window.addEventListener('hashchange', route);
  await route();

  setInterval(() => Store.refreshUnread(), 20000);
}

boot();
