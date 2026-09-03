'use strict';
/* Upload page: pick a video file, or record one live via getUserMedia + MediaRecorder. */

(function () {
  const MAX_RECORD_MS = 60000;
  const MAX_FILE_BYTES = 120 * 1024 * 1024;

  function pickMimeType() {
    const candidates = [
      'video/webm;codecs=vp9,opus',
      'video/webm;codecs=vp8,opus',
      'video/webm',
      'video/mp4',
    ];
    for (const c of candidates) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) return c;
    }
    return '';
  }

  function extFromMime(mime) {
    if (mime.includes('mp4')) return 'mp4';
    return 'webm';
  }

  function uploadWithProgress(formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/videos');
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
      });
      xhr.onload = () => {
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new Error((data && data.error) || `Upload failed (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error('Network error during upload'));
      xhr.send(formData);
    });
  }

  const uploadView = {
    async mount(root) {
      root.classList.add('view-root--page');
      root.innerHTML = `
        <div class="upload-page">
          <h1>Upload video</h1>
          <p class="upload-sub">Post a video to your profile. Recordings play back with sound; seed content on this demo uses generative visuals in place of stock footage.</p>
          <div class="upload-grid">
            <div>
              <div class="upload-source-tabs">
                <button type="button" data-source="file" class="active">Upload file</button>
                <button type="button" data-source="record">Record</button>
              </div>
              <div class="upload-dropzone" id="upload-zone">
                <div id="upload-empty-state">
                  ${icon('upload', 40)}
                  <p>Click to choose a video<br><span class="field-hint">MP4 or WebM, up to 120MB</span></p>
                  <input type="file" accept="video/*" id="file-input">
                </div>
              </div>
              <div id="upload-error" class="field-error" style="margin-top:8px"></div>
            </div>
            <div>
              <div class="field">
                <label for="caption-input">Caption</label>
                <textarea id="caption-input" maxlength="300" placeholder="Describe your video... use #hashtags to reach more people"></textarea>
                <div class="char-count"><span id="char-count">0</span>/300</div>
              </div>
              <div class="field">
                <label for="sound-input">Sound name (optional)</label>
                <input type="text" id="sound-input" maxlength="60" placeholder="e.g. original sound, or reuse a trending sound name">
              </div>
              <div class="upload-actions">
                <a href="#/" data-nav class="btn">Discard</a>
                <button class="btn btn-primary" id="post-btn" disabled>Post</button>
              </div>
              <div id="upload-progress-wrap" style="display:none;margin-top:14px">
                <div class="video-progress" style="position:static;background:#2a2a2a;height:6px;border-radius:3px;overflow:hidden">
                  <div class="video-progress-bar" id="upload-progress-bar" style="background:var(--accent)"></div>
                </div>
                <p class="field-hint" id="upload-progress-text" style="margin-top:6px">Uploading...</p>
              </div>
            </div>
          </div>
        </div>`;

      const zone = root.querySelector('#upload-zone');
      const errorBox = root.querySelector('#upload-error');
      const captionInput = root.querySelector('#caption-input');
      const soundInput = root.querySelector('#sound-input');
      const charCount = root.querySelector('#char-count');
      const postBtn = root.querySelector('#post-btn');
      const sourceBtns = root.querySelectorAll('.upload-source-tabs button');

      let selectedBlob = null; // File or Blob
      let selectedMime = '';
      let objectUrl = null;
      let stream = null;
      let recorder = null;
      let recordTimer = null;
      let recordStart = 0;
      let mode = 'file';

      captionInput.addEventListener('input', () => {
        charCount.textContent = captionInput.value.length;
        updatePostEnabled();
      });

      function updatePostEnabled() {
        postBtn.disabled = !selectedBlob;
      }

      function setError(msg) { errorBox.textContent = msg || ''; }

      function clearSelection() {
        if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
        selectedBlob = null;
        updatePostEnabled();
      }

      function stopCamera() {
        if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
        if (recordTimer) { clearInterval(recordTimer); recordTimer = null; }
      }

      function showFilePreview(file) {
        clearSelection();
        objectUrl = URL.createObjectURL(file);
        selectedBlob = file;
        selectedMime = file.type;
        zone.classList.add('has-preview');
        zone.innerHTML = `
          <video src="${objectUrl}" controls playsinline></video>
          <button type="button" class="upload-remove-btn" id="remove-preview">${icon('x', 16)}</button>`;
        zone.querySelector('#remove-preview').addEventListener('click', (e) => { e.stopPropagation(); renderFileZone(); });
        updatePostEnabled();
      }

      function renderFileZone() {
        stopCamera();
        clearSelection();
        zone.classList.remove('has-preview');
        zone.innerHTML = `
          <div id="upload-empty-state">
            ${icon('upload', 40)}
            <p>Click to choose a video<br><span class="field-hint">MP4 or WebM, up to 120MB</span></p>
            <input type="file" accept="video/*" id="file-input">
          </div>`;
        wireFileInput();
        setError('');
      }

      function wireFileInput() {
        const input = zone.querySelector('#file-input');
        if (!input) return;
        input.addEventListener('change', () => {
          const file = input.files && input.files[0];
          if (!file) return;
          if (!file.type.startsWith('video/')) { setError('Please choose a video file.'); return; }
          if (file.size > MAX_FILE_BYTES) { setError('Video must be smaller than 120MB.'); return; }
          setError('');
          showFilePreview(file);
        });
      }

      async function renderRecordZone() {
        clearSelection();
        zone.classList.remove('has-preview');
        setError('');
        zone.innerHTML = `<div class="section-loading"><div class="loading-spinner"></div></div>`;
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: true });
        } catch (e) {
          zone.innerHTML = `<div style="padding:20px;text-align:center">
            <p>Camera/microphone access was denied or is unavailable in this browser.</p>
            <p class="field-hint">Try "Upload file" instead.</p>
          </div>`;
          return;
        }
        zone.classList.add('has-preview');
        zone.innerHTML = `
          <video id="live-preview" autoplay muted playsinline></video>
          <div class="record-controls">
            <button type="button" class="record-btn" id="record-btn" aria-label="Start recording"></button>
          </div>`;
        const liveVideo = zone.querySelector('#live-preview');
        liveVideo.srcObject = stream;

        const recordBtn = zone.querySelector('#record-btn');
        let chunks = [];
        let recording = false;

        recordBtn.addEventListener('click', () => {
          if (!recording) startRecording(); else stopRecording();
        });

        function startRecording() {
          chunks = [];
          selectedMime = pickMimeType();
          try {
            recorder = new MediaRecorder(stream, selectedMime ? { mimeType: selectedMime } : undefined);
          } catch (e) {
            setError('Recording is not supported in this browser.');
            return;
          }
          recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
          recorder.onstop = () => {
            const blob = new Blob(chunks, { type: selectedMime || 'video/webm' });
            selectedBlob = blob;
            updatePostEnabled();
            objectUrl = URL.createObjectURL(blob);
            stopCamera();
            zone.innerHTML = `
              <video src="${objectUrl}" controls playsinline></video>
              <button type="button" class="upload-remove-btn" id="retake-btn">${icon('cameraFlip', 16)}</button>`;
            zone.querySelector('#retake-btn').addEventListener('click', (e) => { e.stopPropagation(); renderRecordZone(); });
          };
          recorder.start();
          recording = true;
          recordStart = Date.now();
          recordBtn.classList.add('recording');
          const timerEl = document.createElement('div');
          timerEl.className = 'record-timer';
          timerEl.innerHTML = `<span class="dot"></span><span id="record-time">0:00</span>`;
          zone.appendChild(timerEl);
          recordTimer = setInterval(() => {
            const elapsed = Date.now() - recordStart;
            const s = Math.floor(elapsed / 1000);
            const label = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
            const t = zone.querySelector('#record-time');
            if (t) t.textContent = label;
            if (elapsed >= MAX_RECORD_MS) stopRecording();
          }, 250);
        }

        function stopRecording() {
          if (recorder && recorder.state !== 'inactive') recorder.stop();
          recording = false;
          if (recordTimer) { clearInterval(recordTimer); recordTimer = null; }
        }
      }

      sourceBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
          sourceBtns.forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          mode = btn.dataset.source;
          if (mode === 'file') renderFileZone();
          else renderRecordZone();
        });
      });

      wireFileInput();

      postBtn.addEventListener('click', async () => {
        if (!selectedBlob) return;
        postBtn.disabled = true;
        setError('');
        const fd = new FormData();
        const ext = extFromMime(selectedMime || selectedBlob.type || '');
        const filename = selectedBlob.name || `recording.${ext}`;
        fd.append('video', selectedBlob, filename);
        fd.append('caption', captionInput.value.trim());
        fd.append('soundName', soundInput.value.trim());

        const progressWrap = root.querySelector('#upload-progress-wrap');
        const progressBar = root.querySelector('#upload-progress-bar');
        const progressText = root.querySelector('#upload-progress-text');
        progressWrap.style.display = '';
        try {
          const result = await uploadWithProgress(fd, (frac) => {
            progressBar.style.width = `${Math.round(frac * 100)}%`;
            progressText.textContent = frac >= 1 ? 'Processing...' : `Uploading... ${Math.round(frac * 100)}%`;
          });
          Helpers.toast('Video posted!');
          navigate(`#/video/${result.video.id}`);
        } catch (err) {
          setError(err.message || 'Upload failed. Please try again.');
          progressWrap.style.display = 'none';
          postBtn.disabled = false;
        }
      });

      return {
        unmount() {
          stopCamera();
          if (objectUrl) URL.revokeObjectURL(objectUrl);
        },
      };
    },
  };

  window.Views = window.Views || {};
  window.Views.upload = uploadView;
})();
