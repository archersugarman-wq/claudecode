'use strict';
const fs = require('fs');
const path = require('path');
const db = require('./db');
const { hashPassword, verifyPassword, newToken } = require('./auth');
const { parseMultipart } = require('./multipart');
const S = require('./serializers');

const UPLOAD_DIR = path.join(__dirname, 'public', 'uploads');
fs.mkdirSync(UPLOAD_DIR, { recursive: true });

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function requireUser(ctx) {
  if (!ctx.user) throw new HttpError(401, 'You must be logged in to do that.');
  return ctx.user;
}

function clampInt(v, def, min, max) {
  const n = parseInt(v, 10);
  if (Number.isNaN(n)) return def;
  return Math.max(min, Math.min(max, n));
}

function findUserByUsername(state, username) {
  if (!username) return null;
  const norm = String(username).toLowerCase();
  return state.users.find((u) => u.username.toLowerCase() === norm) || null;
}

// ---------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------

const USERNAME_RE = /^[a-z0-9._]{2,24}$/;

async function register(ctx) {
  const { username, password, displayName } = ctx.body || {};
  if (typeof username !== 'string' || typeof password !== 'string') {
    throw new HttpError(400, 'Username and password are required.');
  }
  const uname = username.trim().toLowerCase();
  if (!USERNAME_RE.test(uname)) {
    throw new HttpError(400, 'Username must be 2-24 characters: letters, numbers, "." or "_".');
  }
  if (password.length < 6) throw new HttpError(400, 'Password must be at least 6 characters.');
  const name = (displayName && String(displayName).trim().slice(0, 40)) || username.trim().slice(0, 40);

  const result = await db.mutate((state) => {
    if (findUserByUsername(state, uname)) {
      throw new HttpError(409, 'That username is already taken.');
    }
    const user = {
      id: db.nextId('u'),
      username: uname,
      displayName: name,
      bio: '',
      avatarSeed: (Array.from(uname).reduce((a, c) => a + c.charCodeAt(0), 0) % 14) + 1,
      verified: false,
      passwordHash: hashPassword(password),
      seedFollowers: 0,
      seedFollowing: 0,
      createdAt: Date.now(),
      isSeed: false,
    };
    state.users.push(user);
    const token = newToken();
    state.sessions.push({ token, userId: user.id, createdAt: Date.now() });
    return { user, token };
  });

  ctx.setSessionCookie(result.token);
  return { user: S.publicUser(db.read((s) => s), result.user, result.user.id) };
}

async function login(ctx) {
  const { username, password } = ctx.body || {};
  if (typeof username !== 'string' || typeof password !== 'string') {
    throw new HttpError(400, 'Username and password are required.');
  }
  const result = await db.mutate((state) => {
    const user = findUserByUsername(state, username.trim());
    if (!user || !verifyPassword(password, user.passwordHash)) {
      throw new HttpError(401, 'Invalid username or password.');
    }
    const token = newToken();
    state.sessions.push({ token, userId: user.id, createdAt: Date.now() });
    return { user, token };
  });
  ctx.setSessionCookie(result.token);
  return { user: S.publicUser(db.read((s) => s), result.user, result.user.id) };
}

async function logout(ctx) {
  if (ctx.sessionToken) {
    await db.mutate((state) => {
      state.sessions = state.sessions.filter((s) => s.token !== ctx.sessionToken);
    });
  }
  ctx.clearSessionCookie();
  return { ok: true };
}

async function me(ctx) {
  if (!ctx.user) return { user: null };
  return { user: S.publicUser(db.read((s) => s), ctx.user, ctx.user.id) };
}

// ---------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------

async function getUser(ctx) {
  const state = db.read((s) => s);
  const user = findUserByUsername(state, ctx.params[0]);
  if (!user) throw new HttpError(404, 'User not found.');
  return { user: S.publicUser(state, user, ctx.user && ctx.user.id) };
}

async function updateMe(ctx) {
  const me = requireUser(ctx);
  const { displayName, bio, avatarSeed } = ctx.body || {};
  const result = await db.mutate((state) => {
    const user = state.users.find((u) => u.id === me.id);
    if (typeof displayName === 'string') {
      const trimmed = displayName.trim();
      if (trimmed.length < 1 || trimmed.length > 40) throw new HttpError(400, 'Display name must be 1-40 characters.');
      user.displayName = trimmed;
    }
    if (typeof bio === 'string') {
      if (bio.length > 160) throw new HttpError(400, 'Bio must be 160 characters or fewer.');
      user.bio = bio;
    }
    if (avatarSeed !== undefined) {
      const n = parseInt(avatarSeed, 10);
      if (!Number.isNaN(n)) user.avatarSeed = ((n % 14) + 14) % 14 + 1;
    }
    return user;
  });
  return { user: S.publicUser(db.read((s) => s), result, me.id) };
}

async function toggleFollow(ctx) {
  const me = requireUser(ctx);
  const result = await db.mutate((state) => {
    const target = findUserByUsername(state, ctx.params[0]);
    if (!target) throw new HttpError(404, 'User not found.');
    if (target.id === me.id) throw new HttpError(400, "You can't follow yourself.");
    const existingIdx = state.follows.findIndex((f) => f.followerId === me.id && f.followingId === target.id);
    let nowFollowing;
    if (existingIdx === -1) {
      state.follows.push({ id: db.nextId('f'), followerId: me.id, followingId: target.id, createdAt: Date.now() });
      nowFollowing = true;
      if (!target.isSeed || true) {
        state.notifications.push({
          id: db.nextId('n'), userId: target.id, type: 'follow', actorId: me.id,
          videoId: null, commentId: null, read: false, createdAt: Date.now(),
        });
      }
    } else {
      state.follows.splice(existingIdx, 1);
      nowFollowing = false;
    }
    return { target, nowFollowing };
  });
  const state = db.read((s) => s);
  return {
    following: result.nowFollowing,
    followers: S.followerCount(state, result.target.id),
  };
}

async function userVideos(ctx) {
  const state = db.read((s) => s);
  const user = findUserByUsername(state, ctx.params[0]);
  if (!user) throw new HttpError(404, 'User not found.');
  const all = state.videos.filter((v) => v.authorId === user.id).sort((a, b) => b.createdAt - a.createdAt);
  return paginate(all, ctx, (v) => S.publicVideo(state, v, ctx.user && ctx.user.id));
}

async function userLiked(ctx) {
  const me = requireUser(ctx);
  const state = db.read((s) => s);
  const user = findUserByUsername(state, ctx.params[0]);
  if (!user) throw new HttpError(404, 'User not found.');
  if (user.id !== me.id) throw new HttpError(403, 'Liked videos are private.');
  const likedIds = new Set(state.likes.filter((l) => l.userId === user.id && l.videoId).map((l) => l.videoId));
  const all = state.videos.filter((v) => likedIds.has(v.id)).sort((a, b) => b.createdAt - a.createdAt);
  return paginate(all, ctx, (v) => S.publicVideo(state, v, me.id));
}

async function userFollowers(ctx) {
  const state = db.read((s) => s);
  const user = findUserByUsername(state, ctx.params[0]);
  if (!user) throw new HttpError(404, 'User not found.');
  const rows = state.follows.filter((f) => f.followingId === user.id).sort((a, b) => b.createdAt - a.createdAt);
  const users = rows.map((f) => state.users.find((u) => u.id === f.followerId)).filter(Boolean);
  const page = paginate(users, ctx, (u) => S.publicUser(state, u, ctx.user && ctx.user.id));
  page.seedBaseline = user.seedFollowers;
  return page;
}

async function userFollowing(ctx) {
  const state = db.read((s) => s);
  const user = findUserByUsername(state, ctx.params[0]);
  if (!user) throw new HttpError(404, 'User not found.');
  const rows = state.follows.filter((f) => f.followerId === user.id).sort((a, b) => b.createdAt - a.createdAt);
  const users = rows.map((f) => state.users.find((u) => u.id === f.followingId)).filter(Boolean);
  return paginate(users, ctx, (u) => S.publicUser(state, u, ctx.user && ctx.user.id));
}

// ---------------------------------------------------------------------
// Pagination helper
// ---------------------------------------------------------------------

function paginate(items, ctx, serialize) {
  const cursor = clampInt(ctx.query.cursor, 0, 0, 1e9);
  const limit = clampInt(ctx.query.limit, 8, 1, 24);
  const slice = items.slice(cursor, cursor + limit);
  return {
    items: slice.map(serialize),
    nextCursor: cursor + slice.length,
    hasMore: cursor + slice.length < items.length,
    total: items.length,
  };
}

// ---------------------------------------------------------------------
// Feed / Videos
// ---------------------------------------------------------------------

function scoreVideo(state, video) {
  const ageHours = Math.max(0, (Date.now() - video.createdAt) / 3600000);
  const likes = S.videoLikeCount(state, video.id);
  const comments = S.videoCommentCount(state, video.id);
  const views = video.views || 0;
  const engagement = likes * 1 + comments * 4 + Math.min(views, 3_000_000) * 0.015 + (video.shares || 0) * 2;
  return engagement / Math.pow(ageHours + 2, 1.3);
}

async function feed(ctx) {
  const tab = ctx.query.tab === 'following' ? 'following' : 'foryou';
  const state = db.read((s) => s);
  let list;
  if (tab === 'following') {
    const me = requireUser(ctx);
    const followingIds = new Set(state.follows.filter((f) => f.followerId === me.id).map((f) => f.followingId));
    list = state.videos.filter((v) => followingIds.has(v.authorId)).sort((a, b) => b.createdAt - a.createdAt);
  } else {
    list = state.videos.slice().sort((a, b) => scoreVideo(state, b) - scoreVideo(state, a) || (b.createdAt - a.createdAt));
  }
  return paginate(list, ctx, (v) => S.publicVideo(state, v, ctx.user && ctx.user.id));
}

async function getVideo(ctx) {
  const state = db.read((s) => s);
  const video = state.videos.find((v) => v.id === ctx.params[0]);
  if (!video) throw new HttpError(404, 'Video not found.');
  return { video: S.publicVideo(state, video, ctx.user && ctx.user.id) };
}

const EXT_BY_MIME = {
  'video/webm': '.webm',
  'video/mp4': '.mp4',
  'video/quicktime': '.mov',
  'video/ogg': '.ogv',
  'video/x-matroska': '.mkv',
};

async function createVideo(ctx) {
  const me = requireUser(ctx);
  const { fields, files } = ctx.multipart || { fields: {}, files: [] };
  const caption = (fields.caption || '').toString().slice(0, 300);
  const videoFile = files.find((f) => f.field === 'video');
  if (!videoFile || !videoFile.data || videoFile.data.length === 0) {
    throw new HttpError(400, 'A video file is required.');
  }
  if (!videoFile.mimetype || !videoFile.mimetype.startsWith('video/')) {
    throw new HttpError(400, 'Uploaded file must be a video.');
  }
  if (videoFile.data.length > 120 * 1024 * 1024) {
    throw new HttpError(413, 'Video must be smaller than 120MB.');
  }
  const ext = EXT_BY_MIME[videoFile.mimetype] || '.webm';
  const id = db.nextId('v');
  const filename = `${id}${ext}`;
  await fs.promises.writeFile(path.join(UPLOAD_DIR, filename), videoFile.data);

  const soundNameRaw = (fields.soundName || '').toString().trim().slice(0, 60);

  const result = await db.mutate((state) => {
    let soundId = null;
    let soundName = soundNameRaw || `original sound - ${me.username}`;
    if (soundNameRaw) {
      const existing = state.sounds.find((s) => s.name.toLowerCase() === soundNameRaw.toLowerCase());
      if (existing) { soundId = existing.id; soundName = existing.name; }
    }
    const video = {
      id,
      authorId: me.id,
      caption,
      style: null,
      visualSeed: 0,
      soundId,
      soundName,
      type: 'file',
      url: `/uploads/${filename}`,
      mimetype: videoFile.mimetype,
      seedLikes: 0,
      views: 0,
      shares: 0,
      createdAt: Date.now(),
      isSeed: false,
    };
    state.videos.push(video);
    return video;
  });

  return { video: S.publicVideo(db.read((s) => s), result, me.id) };
}

async function deleteVideo(ctx) {
  const me = requireUser(ctx);
  const removed = await db.mutate((state) => {
    const video = state.videos.find((v) => v.id === ctx.params[0]);
    if (!video) throw new HttpError(404, 'Video not found.');
    if (video.authorId !== me.id) throw new HttpError(403, 'You can only delete your own videos.');
    const commentIds = new Set(state.comments.filter((c) => c.videoId === video.id).map((c) => c.id));
    state.comments = state.comments.filter((c) => c.videoId !== video.id);
    state.likes = state.likes.filter((l) => l.videoId !== video.id && !(l.commentId && commentIds.has(l.commentId)));
    state.notifications = state.notifications.filter((n) => n.videoId !== video.id);
    state.videos = state.videos.filter((v) => v.id !== video.id);
    return video;
  });
  if (removed.type === 'file' && removed.url) {
    const filePath = path.join(__dirname, 'public', removed.url.replace(/^\//, ''));
    fs.promises.unlink(filePath).catch(() => {});
  }
  return { ok: true };
}

async function toggleVideoLike(ctx) {
  const me = requireUser(ctx);
  const result = await db.mutate((state) => {
    const video = state.videos.find((v) => v.id === ctx.params[0]);
    if (!video) throw new HttpError(404, 'Video not found.');
    const idx = state.likes.findIndex((l) => l.userId === me.id && l.videoId === video.id);
    let liked;
    if (idx === -1) {
      state.likes.push({ id: db.nextId('l'), userId: me.id, videoId: video.id, commentId: null, createdAt: Date.now() });
      liked = true;
      if (video.authorId !== me.id) {
        state.notifications.push({
          id: db.nextId('n'), userId: video.authorId, type: 'like', actorId: me.id,
          videoId: video.id, commentId: null, read: false, createdAt: Date.now(),
        });
      }
    } else {
      state.likes.splice(idx, 1);
      liked = false;
    }
    return { video, liked };
  });
  const state = db.read((s) => s);
  return { liked: result.liked, likes: S.videoLikeCount(state, result.video.id) };
}

async function recordView(ctx) {
  const result = await db.mutate((state) => {
    const video = state.videos.find((v) => v.id === ctx.params[0]);
    if (!video) throw new HttpError(404, 'Video not found.');
    video.views = (video.views || 0) + 1;
    return video;
  });
  return { views: result.views };
}

async function recordShare(ctx) {
  const result = await db.mutate((state) => {
    const video = state.videos.find((v) => v.id === ctx.params[0]);
    if (!video) throw new HttpError(404, 'Video not found.');
    video.shares = (video.shares || 0) + 1;
    return video;
  });
  return { shares: result.shares, url: `${ctx.origin}/#/video/${result.id}` };
}

// ---------------------------------------------------------------------
// Comments
// ---------------------------------------------------------------------

async function listComments(ctx) {
  const state = db.read((s) => s);
  const video = state.videos.find((v) => v.id === ctx.params[0]);
  if (!video) throw new HttpError(404, 'Video not found.');
  const all = state.comments.filter((c) => c.videoId === video.id);
  const top = all.filter((c) => !c.parentId)
    .sort((a, b) => (S.commentLikeCount(state, b.id) - S.commentLikeCount(state, a.id)) || (b.createdAt - a.createdAt));
  const byParent = {};
  all.filter((c) => c.parentId).forEach((c) => {
    (byParent[c.parentId] = byParent[c.parentId] || []).push(c);
  });
  const viewerId = ctx.user && ctx.user.id;
  const shaped = top.map((c) => {
    const replies = (byParent[c.id] || []).sort((a, b) => a.createdAt - b.createdAt).map((r) => S.publicComment(state, r, viewerId));
    return Object.assign(S.publicComment(state, c, viewerId), { replies });
  });
  return { comments: shaped, total: all.length };
}

async function createComment(ctx) {
  const me = requireUser(ctx);
  const { text, parentId } = ctx.body || {};
  if (typeof text !== 'string' || !text.trim()) throw new HttpError(400, 'Comment cannot be empty.');
  if (text.length > 300) throw new HttpError(400, 'Comment must be 300 characters or fewer.');

  const result = await db.mutate((state) => {
    const video = state.videos.find((v) => v.id === ctx.params[0]);
    if (!video) throw new HttpError(404, 'Video not found.');
    let normalizedParentId = null;
    let parentComment = null;
    if (parentId) {
      const parent = state.comments.find((c) => c.id === parentId && c.videoId === video.id);
      if (!parent) throw new HttpError(400, 'Comment being replied to no longer exists.');
      // flatten reply-to-reply to a single nesting level, like TikTok does
      normalizedParentId = parent.parentId || parent.id;
      parentComment = state.comments.find((c) => c.id === normalizedParentId) || parent;
    }
    const comment = {
      id: db.nextId('c'),
      videoId: video.id,
      authorId: me.id,
      parentId: normalizedParentId,
      text: text.trim(),
      seedLikes: 0,
      createdAt: Date.now(),
    };
    state.comments.push(comment);
    if (video.authorId !== me.id) {
      state.notifications.push({
        id: db.nextId('n'), userId: video.authorId, type: 'comment', actorId: me.id,
        videoId: video.id, commentId: comment.id, read: false, createdAt: Date.now(),
      });
    }
    if (parentComment && parentComment.authorId !== me.id && parentComment.authorId !== video.authorId) {
      state.notifications.push({
        id: db.nextId('n'), userId: parentComment.authorId, type: 'reply', actorId: me.id,
        videoId: video.id, commentId: comment.id, read: false, createdAt: Date.now(),
      });
    }
    return comment;
  });
  const state = db.read((s) => s);
  return { comment: Object.assign(S.publicComment(state, result, me.id), { replies: [] }) };
}

async function toggleCommentLike(ctx) {
  const me = requireUser(ctx);
  const result = await db.mutate((state) => {
    const comment = state.comments.find((c) => c.id === ctx.params[0]);
    if (!comment) throw new HttpError(404, 'Comment not found.');
    const idx = state.likes.findIndex((l) => l.userId === me.id && l.commentId === comment.id);
    let liked;
    if (idx === -1) {
      state.likes.push({ id: db.nextId('l'), userId: me.id, videoId: null, commentId: comment.id, createdAt: Date.now() });
      liked = true;
    } else {
      state.likes.splice(idx, 1);
      liked = false;
    }
    return { comment, liked };
  });
  const state = db.read((s) => s);
  return { liked: result.liked, likes: S.commentLikeCount(state, result.comment.id) };
}

async function deleteComment(ctx) {
  const me = requireUser(ctx);
  await db.mutate((state) => {
    const comment = state.comments.find((c) => c.id === ctx.params[0]);
    if (!comment) throw new HttpError(404, 'Comment not found.');
    if (comment.authorId !== me.id) throw new HttpError(403, 'You can only delete your own comments.');
    const idsToRemove = new Set([comment.id]);
    if (!comment.parentId) {
      state.comments.filter((c) => c.parentId === comment.id).forEach((c) => idsToRemove.add(c.id));
    }
    state.comments = state.comments.filter((c) => !idsToRemove.has(c.id));
    state.likes = state.likes.filter((l) => !idsToRemove.has(l.commentId));
    state.notifications = state.notifications.filter((n) => !idsToRemove.has(n.commentId));
  });
  return { ok: true };
}

// ---------------------------------------------------------------------
// Search / discover / tags / sounds
// ---------------------------------------------------------------------

function trendingHashtags(state, limit) {
  const counts = new Map();
  state.videos.forEach((v) => {
    S.extractHashtags(v.caption).forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([tag, count]) => ({ tag, count }));
}

async function search(ctx) {
  const state = db.read((s) => s);
  const q = (ctx.query.q || '').toString().trim().toLowerCase();
  const viewerId = ctx.user && ctx.user.id;

  if (!q) {
    const suggested = state.users
      .filter((u) => !viewerId || u.id !== viewerId)
      .filter((u) => !S.isFollowing(state, viewerId, u.id))
      .sort((a, b) => S.followerCount(state, b.id) - S.followerCount(state, a.id))
      .slice(0, 10)
      .map((u) => S.publicUser(state, u, viewerId));
    const discoverVideos = state.videos.slice()
      .sort((a, b) => scoreVideo(state, b) - scoreVideo(state, a))
      .slice(0, 24)
      .map((v) => S.publicVideo(state, v, viewerId));
    return {
      trendingHashtags: trendingHashtags(state, 10),
      trendingSounds: state.sounds.slice().sort((a, b) => S.publicSound(state, b).uses - S.publicSound(state, a).uses).slice(0, 8).map((s) => S.publicSound(state, s)),
      suggestedUsers: suggested,
      videos: discoverVideos,
    };
  }

  const bareTag = q.startsWith('#') ? q.slice(1) : q;
  const users = state.users
    .filter((u) => u.username.toLowerCase().includes(q) || u.displayName.toLowerCase().includes(q))
    .slice(0, 12)
    .map((u) => S.publicUser(state, u, viewerId));
  const videos = state.videos
    .filter((v) => v.caption.toLowerCase().includes(q) || S.extractHashtags(v.caption).includes(bareTag))
    .sort((a, b) => scoreVideo(state, b) - scoreVideo(state, a))
    .slice(0, 24)
    .map((v) => S.publicVideo(state, v, viewerId));
  const sounds = state.sounds
    .filter((s) => s.name.toLowerCase().includes(q))
    .slice(0, 8)
    .map((s) => S.publicSound(state, s));

  return { users, videos, sounds, query: q };
}

async function tagVideos(ctx) {
  const state = db.read((s) => s);
  const tag = decodeURIComponent(ctx.params[0]).toLowerCase();
  const all = state.videos
    .filter((v) => S.extractHashtags(v.caption).includes(tag))
    .sort((a, b) => scoreVideo(state, b) - scoreVideo(state, a));
  const page = paginate(all, ctx, (v) => S.publicVideo(state, v, ctx.user && ctx.user.id));
  page.tag = tag;
  return page;
}

async function getSound(ctx) {
  const state = db.read((s) => s);
  const sound = state.sounds.find((s) => s.id === ctx.params[0]);
  if (!sound) throw new HttpError(404, 'Sound not found.');
  return { sound: S.publicSound(state, sound) };
}

async function soundVideos(ctx) {
  const state = db.read((s) => s);
  const sound = state.sounds.find((s) => s.id === ctx.params[0]);
  if (!sound) throw new HttpError(404, 'Sound not found.');
  const all = state.videos.filter((v) => v.soundId === sound.id).sort((a, b) => scoreVideo(state, b) - scoreVideo(state, a));
  const page = paginate(all, ctx, (v) => S.publicVideo(state, v, ctx.user && ctx.user.id));
  page.sound = S.publicSound(state, sound);
  return page;
}

// ---------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------

const NOTIF_TEXT = {
  follow: 'started following you',
  like: 'liked your video',
  comment: 'commented on your video',
  reply: 'replied to your comment',
};

async function listNotifications(ctx) {
  const me = requireUser(ctx);
  const state = db.read((s) => s);
  const mine = state.notifications
    .filter((n) => n.userId === me.id)
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 100);
  const items = mine.map((n) => {
    const actor = state.users.find((u) => u.id === n.actorId);
    const video = n.videoId ? state.videos.find((v) => v.id === n.videoId) : null;
    const comment = n.commentId ? state.comments.find((c) => c.id === n.commentId) : null;
    return {
      id: n.id,
      type: n.type,
      text: NOTIF_TEXT[n.type] || '',
      read: !!n.read,
      createdAt: n.createdAt,
      actor: actor ? { username: actor.username, displayName: actor.displayName, avatarSeed: actor.avatarSeed, verified: !!actor.verified } : null,
      video: video ? { id: video.id, caption: video.caption, style: video.style, visualSeed: video.visualSeed } : null,
      commentText: comment ? comment.text : null,
    };
  }).filter((n) => n.actor);
  return { notifications: items, unread: items.filter((n) => !n.read).length };
}

async function readAllNotifications(ctx) {
  const me = requireUser(ctx);
  await db.mutate((state) => {
    state.notifications.forEach((n) => { if (n.userId === me.id) n.read = true; });
  });
  return { ok: true };
}

module.exports = {
  HttpError,
  routes: [
    ['POST', /^\/api\/auth\/register$/, register],
    ['POST', /^\/api\/auth\/login$/, login],
    ['POST', /^\/api\/auth\/logout$/, logout],
    ['GET', /^\/api\/me$/, me],

    ['GET', /^\/api\/feed$/, feed],
    ['GET', /^\/api\/videos\/([^/]+)$/, getVideo],
    ['POST', /^\/api\/videos$/, createVideo],
    ['DELETE', /^\/api\/videos\/([^/]+)$/, deleteVideo],
    ['POST', /^\/api\/videos\/([^/]+)\/like$/, toggleVideoLike],
    ['POST', /^\/api\/videos\/([^/]+)\/view$/, recordView],
    ['POST', /^\/api\/videos\/([^/]+)\/share$/, recordShare],
    ['GET', /^\/api\/videos\/([^/]+)\/comments$/, listComments],
    ['POST', /^\/api\/videos\/([^/]+)\/comments$/, createComment],

    ['POST', /^\/api\/comments\/([^/]+)\/like$/, toggleCommentLike],
    ['DELETE', /^\/api\/comments\/([^/]+)$/, deleteComment],

    ['GET', /^\/api\/users\/([^/]+)$/, getUser],
    ['PATCH', /^\/api\/users\/me$/, updateMe],
    ['POST', /^\/api\/users\/([^/]+)\/follow$/, toggleFollow],
    ['GET', /^\/api\/users\/([^/]+)\/videos$/, userVideos],
    ['GET', /^\/api\/users\/([^/]+)\/liked$/, userLiked],
    ['GET', /^\/api\/users\/([^/]+)\/followers$/, userFollowers],
    ['GET', /^\/api\/users\/([^/]+)\/following$/, userFollowing],

    ['GET', /^\/api\/search$/, search],
    ['GET', /^\/api\/tags\/([^/]+)\/videos$/, tagVideos],
    ['GET', /^\/api\/sounds\/([^/]+)$/, getSound],
    ['GET', /^\/api\/sounds\/([^/]+)\/videos$/, soundVideos],

    ['GET', /^\/api\/notifications$/, listNotifications],
    ['POST', /^\/api\/notifications\/read-all$/, readAllNotifications],
  ],
};
