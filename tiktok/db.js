'use strict';
/**
 * Tiny JSON-file datastore with atomic writes and an in-process write queue
 * (so concurrent requests can't interleave a read-modify-write and clobber
 * each other). Not built for scale -- built for a single-process demo app.
 */
const fs = require('fs');
const path = require('path');

const DB_PATH = path.join(__dirname, 'data', 'db.json');
const TMP_PATH = DB_PATH + '.tmp';
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

const EMPTY = {
  users: [],
  videos: [],
  comments: [],
  likes: [],
  follows: [],
  sessions: [],
  notifications: [],
  sounds: [],
};

function load() {
  try {
    const raw = fs.readFileSync(DB_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    // Ensure every collection exists even if the file predates a field.
    return Object.assign({}, EMPTY, parsed);
  } catch (err) {
    if (err.code === 'ENOENT') return Object.assign({}, EMPTY);
    // Corrupt file -- back it up rather than silently eating data.
    try {
      fs.copyFileSync(DB_PATH, DB_PATH + '.corrupt.' + Date.now());
    } catch (_) {}
    return Object.assign({}, EMPTY);
  }
}

let state = load();
let writeChain = Promise.resolve();

function persist() {
  // Atomic write: write to tmp file then rename, so a crash mid-write never
  // leaves db.json truncated/partial.
  const json = JSON.stringify(state, null, 2);
  return new Promise((resolve, reject) => {
    fs.writeFile(TMP_PATH, json, 'utf8', (err) => {
      if (err) return reject(err);
      fs.rename(TMP_PATH, DB_PATH, (err2) => {
        if (err2) return reject(err2);
        resolve();
      });
    });
  });
}

/**
 * Run `fn(state)` exclusively with respect to all other mutate() calls,
 * then persist to disk. `fn` may mutate `state` in place and/or return a
 * value to hand back to the caller.
 */
function mutate(fn) {
  const run = writeChain.then(async () => {
    const result = await fn(state);
    await persist();
    return result;
  });
  // Keep chaining even if this particular mutation rejected, so one bad
  // request doesn't wedge every future write.
  writeChain = run.catch(() => {});
  return run;
}

function read(fn) {
  return fn(state);
}

let _id = 0;
function nextId(prefix) {
  _id += 1;
  return `${prefix}_${Date.now().toString(36)}${(_id).toString(36)}`;
}

module.exports = { read, mutate, nextId, DB_PATH };
