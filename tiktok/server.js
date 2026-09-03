'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

const db = require('./db');
const { parseCookies } = require('./auth');
const { parseMultipart, readBody } = require('./multipart');
const { seedIfEmpty } = require('./seed');
const { HttpError, routes } = require('./routes');

const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;
const PUBLIC_DIR = path.join(__dirname, 'public');
const SESSION_COOKIE = 'tt_session';
const SESSION_MAX_AGE_S = 60 * 60 * 24 * 30; // 30 days

const seedResult = seedIfEmpty(db);
Promise.resolve(seedResult).then((r) => {
  if (r && r.seeded) console.log(`[seed] created ${r.users} users, ${r.videos} videos`);
});

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.webm': 'video/webm',
  '.mp4': 'video/mp4',
  '.mov': 'video/quicktime',
  '.ogv': 'video/ogg',
  '.mkv': 'video/x-matroska',
  '.woff2': 'font/woff2',
};

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

function safeJoin(base, requestPath) {
  const decoded = decodeURIComponent(requestPath);
  const target = path.normalize(path.join(base, decoded));
  if (!target.startsWith(base)) return null; // path traversal guard
  return target;
}

function serveStatic(req, res, pathname) {
  const rel = pathname === '/' ? '/index.html' : pathname;
  const filePath = safeJoin(PUBLIC_DIR, rel);
  if (!filePath) {
    sendJson(res, 400, { error: 'Bad request' });
    return;
  }
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) {
      // SPA fallback: unknown non-API GET paths get index.html so hash
      // routes and manual reloads still work.
      if (req.method === 'GET') {
        const indexPath = path.join(PUBLIC_DIR, 'index.html');
        fs.readFile(indexPath, (err2, data) => {
          if (err2) return sendJson(res, 404, { error: 'Not found' });
          res.writeHead(200, { 'Content-Type': MIME['.html'], 'Content-Length': data.length });
          res.end(data);
        });
      } else {
        sendJson(res, 404, { error: 'Not found' });
      }
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const mime = MIME[ext] || 'application/octet-stream';
    const range = req.headers.range;

    if (range) {
      const m = /bytes=(\d*)-(\d*)/.exec(range);
      let startB = m && m[1] ? parseInt(m[1], 10) : 0;
      let endB = m && m[2] ? parseInt(m[2], 10) : stat.size - 1;
      if (Number.isNaN(startB)) startB = 0;
      if (Number.isNaN(endB) || endB >= stat.size) endB = stat.size - 1;
      if (startB > endB || startB >= stat.size) {
        res.writeHead(416, { 'Content-Range': `bytes */${stat.size}` });
        res.end();
        return;
      }
      res.writeHead(206, {
        'Content-Type': mime,
        'Content-Length': endB - startB + 1,
        'Content-Range': `bytes ${startB}-${endB}/${stat.size}`,
        'Accept-Ranges': 'bytes',
        'Cache-Control': ext === '.html' ? 'no-store' : 'public, max-age=3600',
      });
      fs.createReadStream(filePath, { start: startB, end: endB }).pipe(res);
      return;
    }

    res.writeHead(200, {
      'Content-Type': mime,
      'Content-Length': stat.size,
      'Accept-Ranges': 'bytes',
      'Cache-Control': ext === '.html' ? 'no-store' : 'public, max-age=3600',
    });
    fs.createReadStream(filePath).pipe(res);
  });
}

function resolveSessionUser(cookies) {
  const token = cookies[SESSION_COOKIE];
  if (!token) return { token: null, user: null };
  const state = db.read((s) => s);
  const session = state.sessions.find((s) => s.token === token);
  if (!session) return { token: null, user: null };
  const expired = Date.now() - session.createdAt > SESSION_MAX_AGE_S * 1000;
  if (expired) return { token: null, user: null };
  const user = state.users.find((u) => u.id === session.userId) || null;
  return { token, user };
}

async function handleApi(req, res, pathname, query) {
  const method = req.method;
  const route = routes.find(([m, re]) => m === method && re.test(pathname));
  if (!route) {
    sendJson(res, 404, { error: 'Unknown API route' });
    return;
  }
  const [, re, handler] = route;
  const match = re.exec(pathname);
  const params = match.slice(1);

  const cookies = parseCookies(req.headers.cookie);
  const { token, user } = resolveSessionUser(cookies);
  const proto = (req.headers['x-forwarded-proto'] || 'http').split(',')[0].trim();
  const origin = `${proto}://${req.headers.host}`;

  const ctx = {
    req, res, params, query, user, sessionToken: token, origin,
    body: null,
    multipart: null,
    setSessionCookie(newToken) {
      res.setHeader('Set-Cookie', `${SESSION_COOKIE}=${newToken}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_MAX_AGE_S}`);
    },
    clearSessionCookie() {
      res.setHeader('Set-Cookie', `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`);
    },
  };

  try {
    const contentType = req.headers['content-type'] || '';
    if (method === 'POST' || method === 'PATCH' || method === 'PUT') {
      if (contentType.startsWith('multipart/form-data')) {
        ctx.multipart = await parseMultipart(req, { maxBytes: 150 * 1024 * 1024 });
      } else if (req.headers['content-length'] !== '0') {
        const raw = await readBody(req, 2 * 1024 * 1024);
        if (raw.length) {
          try {
            ctx.body = JSON.parse(raw.toString('utf8'));
          } catch (_) {
            throw new HttpError(400, 'Malformed JSON body.');
          }
        } else {
          ctx.body = {};
        }
      } else {
        ctx.body = {};
      }
    }

    const result = await handler(ctx);
    sendJson(res, 200, result || {});
  } catch (err) {
    if (err instanceof HttpError) {
      sendJson(res, err.status, { error: err.message });
    } else if (err && err.status) {
      sendJson(res, err.status, { error: err.message || 'Request failed' });
    } else {
      console.error('[api error]', method, pathname, err);
      sendJson(res, 500, { error: 'Internal server error' });
    }
  }
}

const server = http.createServer((req, res) => {
  let url;
  try {
    url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  } catch (_) {
    res.writeHead(400);
    res.end('Bad request');
    return;
  }
  const pathname = decodeURIComponent(url.pathname);
  const query = Object.fromEntries(url.searchParams.entries());

  if (pathname.startsWith('/api/')) {
    handleApi(req, res, pathname, query);
    return;
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    sendJson(res, 405, { error: 'Method not allowed' });
    return;
  }
  serveStatic(req, res, pathname);
});

server.listen(PORT, () => {
  console.log(`TikTok clone running at http://localhost:${PORT}`);
});

module.exports = server;
