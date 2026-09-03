'use strict';

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(path, Object.assign({ credentials: 'same-origin' }, opts));
  let data = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch (_) { data = null; }
  }
  if (!res.ok) {
    throw new ApiError(res.status, (data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

function apiGet(path) {
  return apiFetch(path, { method: 'GET' });
}

function apiJson(path, method, body) {
  return apiFetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
}

function apiUpload(path, formData) {
  return apiFetch(path, { method: 'POST', body: formData });
}

function qs(params) {
  const usp = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') usp.set(k, v);
  });
  const s = usp.toString();
  return s ? `?${s}` : '';
}

const Api = {
  me: () => apiGet('/api/me'),
  register: (username, password, displayName) => apiJson('/api/auth/register', 'POST', { username, password, displayName }),
  login: (username, password) => apiJson('/api/auth/login', 'POST', { username, password }),
  logout: () => apiJson('/api/auth/logout', 'POST'),

  feed: (tab, cursor, limit) => apiGet(`/api/feed${qs({ tab, cursor, limit })}`),
  getVideo: (id) => apiGet(`/api/videos/${id}`),
  uploadVideo: (formData) => apiUpload('/api/videos', formData),
  deleteVideo: (id) => apiFetch(`/api/videos/${id}`, { method: 'DELETE' }),
  likeVideo: (id) => apiJson(`/api/videos/${id}/like`, 'POST'),
  viewVideo: (id) => apiJson(`/api/videos/${id}/view`, 'POST'),
  shareVideo: (id) => apiJson(`/api/videos/${id}/share`, 'POST'),

  comments: (videoId) => apiGet(`/api/videos/${videoId}/comments`),
  addComment: (videoId, text, parentId) => apiJson(`/api/videos/${videoId}/comments`, 'POST', { text, parentId }),
  likeComment: (id) => apiJson(`/api/comments/${id}/like`, 'POST'),
  deleteComment: (id) => apiFetch(`/api/comments/${id}`, { method: 'DELETE' }),

  getUser: (username) => apiGet(`/api/users/${username}`),
  updateMe: (fields) => apiFetch('/api/users/me', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fields) }),
  follow: (username) => apiJson(`/api/users/${username}/follow`, 'POST'),
  userVideos: (username, cursor, limit) => apiGet(`/api/users/${username}/videos${qs({ cursor, limit })}`),
  userLiked: (username, cursor, limit) => apiGet(`/api/users/${username}/liked${qs({ cursor, limit })}`),
  userFollowers: (username, cursor, limit) => apiGet(`/api/users/${username}/followers${qs({ cursor, limit })}`),
  userFollowing: (username, cursor, limit) => apiGet(`/api/users/${username}/following${qs({ cursor, limit })}`),

  search: (q) => apiGet(`/api/search${qs({ q })}`),
  tagVideos: (tag, cursor, limit) => apiGet(`/api/tags/${encodeURIComponent(tag)}/videos${qs({ cursor, limit })}`),
  sound: (id) => apiGet(`/api/sounds/${id}`),
  soundVideos: (id, cursor, limit) => apiGet(`/api/sounds/${id}/videos${qs({ cursor, limit })}`),

  notifications: () => apiGet('/api/notifications'),
  readAllNotifications: () => apiJson('/api/notifications/read-all', 'POST'),
};

window.Api = Api;
window.ApiError = ApiError;
