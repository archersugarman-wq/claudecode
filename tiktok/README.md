# TikTok Clone (demo build)

A working, self-contained recreation of TikTok's core web experience: a
vertical snap-scrolling video feed with autoplay, likes, nested comments,
follows, profiles, uploads (file or live webcam recording), hashtags,
sounds, search/discover, and notifications.

This is **not** the real TikTok's codebase (that's proprietary, runs on
years of infrastructure, a trained recommendation model, native mobile
apps, and a licensed music catalog) — it's a from-scratch clone of the
product experience, built to run as a single Node process with zero
external runtime dependencies.

## Run it

```
node server.js
```

Then open `http://localhost:3000`. Port defaults to 3000; override with
`PORT=xxxx node server.js`.

On first boot the server seeds `data/db.json` with 14 creator accounts (one
password for all of them: `password123`, e.g. username `chefmarco`) and 42
posts spread across cooking/coding/travel/fitness/art/pets/music/comedy/
DIY/study/gaming/nature/fashion/dance niches, with comments and a light
follow graph. Delete `data/db.json` and restart to reseed from scratch.

## How it's built

- **Backend**: plain `http` module, no framework. `server.js` routes
  requests, `routes.js` holds the REST API handlers, `db.js` is a tiny
  JSON-file datastore with atomic writes and an in-process write queue,
  `auth.js` does scrypt password hashing + cookie sessions, `multipart.js`
  is a hand-rolled `multipart/form-data` parser for video uploads.
- **Frontend**: vanilla JS SPA (no build step, no framework) with a
  hash-based router (`app.js`), a fetch wrapper (`api.js`), and one file
  per view under `public/views/`.
- **Seed video content**: there's no stock footage to source for a demo
  like this, so seed posts render deterministic, looping generative
  animations on `<canvas>` (`canvas-video.js`) instead — styled per
  creator niche (plasma, matrix rain, aurora, waveform, particles, a
  bouncing-blob "screensaver", an audio-bar visualizer, confetti,
  starfield, a rotating tunnel). **Real uploads are real video**: use
  "Upload file" or "Record" (getUserMedia + MediaRecorder, mic included)
  on the Upload page, and it plays back through an actual `<video>`
  element with working seek (HTTP Range support) and sound.

## What's implemented

Auth (register/login/logout, sessions), For You / Following feeds with
autoplay-on-scroll and infinite loading, like/comment (with one level of
replies)/share/follow, video upload via file picker or live recording,
profile pages (videos + private "liked" tab, follower/following lists,
edit profile), hashtag and sound pages, search + discover (trending
hashtags/sounds, suggested accounts), notifications, and a responsive
layout (desktop sidebar / mobile bottom tabs).

## Deliberately out of scope

Direct messages, duets/stitches, a real recommendation model (the For You
ranking is a simple engagement/recency heuristic), livestreaming, a native
mobile app, and multi-process/horizontal scaling (the datastore is a
single JSON file — fine for a demo, not for production traffic).
