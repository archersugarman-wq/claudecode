'use strict';
/**
 * Minimal binary-safe multipart/form-data parser. No external deps.
 * Buffers the whole request body (bounded by maxBytes) then splits on the
 * boundary. Good enough for a demo app's video-upload endpoint; not meant
 * for huge streaming uploads.
 */

const CRLF = '\r\n';

function getBoundary(contentType) {
  if (!contentType) return null;
  const match = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(contentType);
  if (!match) return null;
  return (match[1] || match[2] || '').trim();
}

function readBody(req, maxBytes) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let total = 0;
    let aborted = false;
    req.on('data', (chunk) => {
      if (aborted) return;
      total += chunk.length;
      if (total > maxBytes) {
        aborted = true;
        const err = new Error('Payload too large');
        err.status = 413;
        reject(err);
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      if (aborted) return;
      resolve(Buffer.concat(chunks, total));
    });
    req.on('error', (err) => {
      if (!aborted) reject(err);
    });
  });
}

function parseHeaders(headerBlock) {
  const headers = {};
  headerBlock.split(CRLF).forEach((line) => {
    const idx = line.indexOf(':');
    if (idx === -1) return;
    const key = line.slice(0, idx).trim().toLowerCase();
    const val = line.slice(idx + 1).trim();
    headers[key] = val;
  });
  return headers;
}

function parseContentDisposition(value) {
  const out = {};
  if (!value) return out;
  value.split(';').forEach((part) => {
    const seg = part.trim();
    const eq = seg.indexOf('=');
    if (eq === -1) {
      if (!out.type) out.type = seg;
      return;
    }
    const k = seg.slice(0, eq).trim();
    let v = seg.slice(eq + 1).trim();
    if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1);
    out[k] = v;
  });
  return out;
}

/**
 * @returns {Promise<{fields: Object<string,string>, files: Array<{field:string, filename:string, mimetype:string, data:Buffer}>}>}
 */
async function parseMultipart(req, { maxBytes = 150 * 1024 * 1024 } = {}) {
  const contentType = req.headers['content-type'] || '';
  const boundary = getBoundary(contentType);
  if (!boundary) {
    const err = new Error('Missing multipart boundary');
    err.status = 400;
    throw err;
  }
  const body = await readBody(req, maxBytes);
  const boundaryBuf = Buffer.from('--' + boundary);

  const fields = {};
  const files = [];

  let start = body.indexOf(boundaryBuf);
  if (start === -1) return { fields, files };

  while (true) {
    const partStart = start + boundaryBuf.length;
    // Check for terminal boundary "--boundary--"
    if (body[partStart] === 0x2d && body[partStart + 1] === 0x2d) break;

    const nextBoundary = body.indexOf(boundaryBuf, partStart);
    if (nextBoundary === -1) break;

    // Part bytes are between partStart+CRLF and nextBoundary-CRLF
    let partBody = body.slice(partStart + 2, nextBoundary - 2); // skip leading CRLF, trailing CRLF before boundary
    const headerEnd = partBody.indexOf(Buffer.from(CRLF + CRLF));
    if (headerEnd !== -1) {
      const headerBlock = partBody.slice(0, headerEnd).toString('utf8');
      const data = partBody.slice(headerEnd + 4);
      const headers = parseHeaders(headerBlock);
      const disposition = parseContentDisposition(headers['content-disposition']);
      if (disposition.filename !== undefined) {
        files.push({
          field: disposition.name || '',
          filename: disposition.filename,
          mimetype: headers['content-type'] || 'application/octet-stream',
          data,
        });
      } else if (disposition.name) {
        fields[disposition.name] = data.toString('utf8');
      }
    }

    start = nextBoundary;
  }

  return { fields, files };
}

module.exports = { parseMultipart, readBody, getBoundary };
