'use strict';
/* For You / Following feed: vertical snap-scroll, autoplay-on-view, action rail. */

(function () {
  function getMuted() {
    try { return localStorage.getItem('tt_muted') !== 'false'; } catch (e) { return true; }
  }
  function setMuted(v) {
    try { localStorage.setItem('tt_muted', String(v)); } catch (e) { /* ignore */ }
  }

  function soundDiscHtml(video) {
    return `<div class="action-sound-disc">${icon('music', 16)}</div>`;
  }

  function videoMetaHtml(video) {
    const soundHref = video.soundId ? `#/sound/${video.soundId}` : `#/user/${video.author.username}`;
    const followPill = (!video.author.isSelf && !video.author.isFollowing && Store.currentUser)
      ? `<button class="video-follow-inline" data-action="follow">Follow</button>` : '';
    return `
      <div class="video-author-row">
        <a href="#/user/${video.author.username}" data-nav class="avatar">${Helpers.avatarSvg(video.author.avatarSeed, video.author.displayName, 30)}</a>
        <a href="#/user/${video.author.username}" data-nav>@${Helpers.escapeHtml(video.author.username)}</a>
        ${video.author.verified ? icon('checkBadge', 15) : ''}
        ${followPill}
      </div>
      <p class="video-caption">${Helpers.renderCaption(video.caption)}</p>
      <div class="video-sound-row">${icon('music', 13)} <a href="${soundHref}" data-nav>${Helpers.escapeHtml(video.soundName)}</a></div>
    `;
  }

  function actionRailHtml(video) {
    const authed = !!Store.currentUser;
    const showPlus = authed && !video.author.isSelf && !video.author.isFollowing;
    return `
      <a href="#/user/${video.author.username}" data-nav class="action-avatar">
        ${Helpers.avatarSvg(video.author.avatarSeed, video.author.displayName, 46)}
        ${showPlus ? `<span class="avatar-plus" data-action="follow">${icon('plus', 12)}</span>` : ''}
      </a>
      <button class="action-btn ${video.isLiked ? 'liked' : ''}" data-action="like">
        <span class="action-circle">${icon(video.isLiked ? 'heartFilled' : 'heart', 26)}</span>
        <span class="count" data-role="like-count">${Helpers.formatCount(video.stats.likes)}</span>
      </button>
      <button class="action-btn" data-action="comment">
        <span class="action-circle">${icon('comment', 24)}</span>
        <span class="count" data-role="comment-count">${Helpers.formatCount(video.stats.comments)}</span>
      </button>
      <button class="action-btn" data-action="share">
        <span class="action-circle">${icon('share', 24)}</span>
        <span class="count" data-role="share-count">${Helpers.formatCount(video.stats.shares)}</span>
      </button>
      <button class="action-btn" data-action="more">
        <span class="action-circle">${icon('more', 22)}</span>
      </button>
      <a href="${video.soundId ? '#/sound/' + video.soundId : '#/user/' + video.author.username}" data-nav>${soundDiscHtml(video)}</a>
    `;
  }

  function buildCard(video, hooks) {
    hooks = hooks || {};
    const isFile = video.type === 'file';
    const card = Helpers.el(`
      <section class="video-card" data-video-id="${video.id}">
        <div class="video-frame">
          ${isFile
            ? `<video src="${video.url}" loop playsinline muted preload="metadata"></video>`
            : `<canvas></canvas>`}
          <div class="tap-target" data-action="toggle-play"></div>
          ${isFile ? `<button class="video-mute-btn" data-action="mute">${icon(getMuted() ? 'volumeMute' : 'volumeUp', 18)}</button>` : ''}
          <div class="video-play-badge">${icon('play', 56)}</div>
          ${isFile ? `<div class="video-progress"><div class="video-progress-bar"></div></div>` : ''}
          <div class="video-meta">${videoMetaHtml(video)}</div>
        </div>
        <div class="action-rail">${actionRailHtml(video)}</div>
      </section>`);

    let renderer = null;
    let mediaEl = null;
    let counted = false;
    let paused = false;

    if (isFile) {
      mediaEl = card.querySelector('video');
      mediaEl.muted = getMuted();
      mediaEl.addEventListener('timeupdate', () => {
        if (!mediaEl.duration) return;
        const bar = card.querySelector('.video-progress-bar');
        if (bar) bar.style.width = `${(mediaEl.currentTime / mediaEl.duration) * 100}%`;
      });
    } else {
      const canvas = card.querySelector('canvas');
      renderer = window.createProceduralVideo(canvas, video.style, video.visualSeed);
    }

    function markViewed() {
      if (counted) return;
      counted = true;
      Api.viewVideo(video.id).catch(() => {});
    }

    function play() {
      paused = false;
      card.querySelector('.video-play-badge').classList.remove('show');
      if (mediaEl) mediaEl.play().catch(() => {});
      if (renderer) renderer.start();
    }
    function pause() {
      paused = true;
      card.querySelector('.video-play-badge').classList.add('show');
      if (mediaEl) mediaEl.pause();
      if (renderer) renderer.stop();
    }
    function enter() {
      markViewed();
      if (!paused) play();
    }
    function leave() {
      if (mediaEl) mediaEl.pause();
      if (renderer) renderer.stop();
    }
    function togglePlay() {
      if (paused) play(); else pause();
    }
    function destroy() {
      if (renderer) renderer.destroy();
      if (mediaEl) { mediaEl.pause(); mediaEl.removeAttribute('src'); mediaEl.load(); }
    }

    // -------- interactions --------
    card.querySelector('[data-action="toggle-play"]').addEventListener('click', togglePlay);

    const muteBtn = card.querySelector('[data-action="mute"]');
    if (muteBtn) {
      muteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const next = !getMuted();
        setMuted(next);
        document.querySelectorAll('.video-card video').forEach((v) => { v.muted = next; });
        document.querySelectorAll('.video-mute-btn').forEach((b) => { b.innerHTML = icon(next ? 'volumeMute' : 'volumeUp', 18); });
      });
    }

    function requireLogin(action) {
      Helpers.toast(`Log in to ${action}`);
      navigate('#/login');
    }

    card.querySelector('[data-action="like"]').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!Store.currentUser) return requireLogin('like videos');
      const btn = e.currentTarget;
      const wasLiked = btn.classList.contains('liked');
      btn.classList.toggle('liked');
      btn.querySelector('.action-circle').innerHTML = icon(wasLiked ? 'heart' : 'heartFilled', 26);
      const countEl = btn.querySelector('[data-role="like-count"]');
      const cur = video.stats.likes;
      countEl.textContent = Helpers.formatCount(wasLiked ? cur - 1 : cur + 1);
      try {
        const res = await Api.likeVideo(video.id);
        video.stats.likes = res.likes;
        video.isLiked = res.liked;
        countEl.textContent = Helpers.formatCount(res.likes);
        btn.classList.toggle('liked', res.liked);
        btn.querySelector('.action-circle').innerHTML = icon(res.liked ? 'heartFilled' : 'heart', 26);
      } catch (err) {
        btn.classList.toggle('liked', wasLiked);
        countEl.textContent = Helpers.formatCount(cur);
        Helpers.toast(err.message || 'Failed to like video');
      }
    });

    card.querySelector('[data-action="comment"]').addEventListener('click', (e) => {
      e.stopPropagation();
      openCommentsDrawer(video, (newCount) => {
        video.stats.comments = newCount;
        card.querySelector('[data-role="comment-count"]').textContent = Helpers.formatCount(newCount);
      });
    });

    card.querySelector('[data-action="share"]').addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        const res = await Api.shareVideo(video.id);
        video.stats.shares = res.shares;
        card.querySelector('[data-role="share-count"]').textContent = Helpers.formatCount(res.shares);
        openShareSheet(res.url);
      } catch (err) {
        Helpers.toast(err.message || 'Failed to share');
      }
    });

    card.querySelector('[data-action="more"]').addEventListener('click', (e) => {
      e.stopPropagation();
      openVideoMenu(video, () => {
        destroy();
        card.remove();
        if (hooks.onRemoved) hooks.onRemoved();
      });
    });

    card.querySelectorAll('[data-action="follow"]').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        e.preventDefault();
        if (!Store.currentUser) return requireLogin('follow creators');
        try {
          const res = await Api.follow(video.author.username);
          video.author.isFollowing = res.following;
          card.querySelectorAll('[data-action="follow"]').forEach((b) => { b.style.display = res.following ? 'none' : ''; });
        } catch (err) {
          Helpers.toast(err.message || 'Failed to follow');
        }
      });
    });

    return { el: card, enter, leave, destroy, video };
  }

  function openShareSheet(url) {
    const wrap = Helpers.el(`
      <div class="share-sheet">
        <h3>Share to</h3>
        <div class="share-options">
          <button data-copy><span class="share-option-icon">${icon('send', 20)}</span>Copy link</button>
        </div>
        <div class="share-link-row">
          <input type="text" readonly value="${Helpers.escapeHtml(url)}">
          <button class="btn btn-sm" data-copy>Copy</button>
        </div>
      </div>`);
    Modal.open(wrap);
    wrap.querySelectorAll('[data-copy]').forEach((b) => b.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(url);
        Helpers.toast('Link copied to clipboard');
      } catch (e) {
        wrap.querySelector('input').select();
        Helpers.toast('Select and copy the link');
      }
      Modal.close();
    }));
  }

  function openVideoMenu(video, onDeleted) {
    const isOwn = video.author.isSelf;
    const wrap = Helpers.el(`
      <div class="video-menu-sheet">
        <button data-action="not-interested">${icon('x', 18)} Not interested</button>
        <button data-action="report">${icon('bell', 18)} Report</button>
        ${isOwn ? `<button data-action="delete" class="danger">${icon('trash', 18)} Delete video</button>` : ''}
      </div>`);
    Modal.open(wrap);
    wrap.querySelector('[data-action="not-interested"]').addEventListener('click', () => { Modal.close(); Helpers.toast("Got it, you'll see less of this"); });
    wrap.querySelector('[data-action="report"]').addEventListener('click', () => { Modal.close(); Helpers.toast('Thanks for the report'); });
    const delBtn = wrap.querySelector('[data-action="delete"]');
    if (delBtn) delBtn.addEventListener('click', () => {
      Modal.close();
      confirmDialog('Delete video?', 'This can\'t be undone.', 'Delete').then(async (ok) => {
        if (!ok) return;
        try {
          await Api.deleteVideo(video.id);
          Helpers.toast('Video deleted');
          if (onDeleted) onDeleted();
        } catch (err) {
          Helpers.toast(err.message || 'Failed to delete video');
        }
      });
    });
  }

  function confirmDialog(title, body, confirmLabel) {
    return new Promise((resolve) => {
      const wrap = Helpers.el(`
        <div class="dialog-card">
          <h3>${Helpers.escapeHtml(title)}</h3>
          <p>${Helpers.escapeHtml(body)}</p>
          <div class="dialog-actions">
            <button class="btn" data-no>Cancel</button>
            <button class="btn btn-danger" data-yes>${Helpers.escapeHtml(confirmLabel)}</button>
          </div>
        </div>`);
      let settled = false;
      Modal.open(wrap, { onClose: () => { if (!settled) resolve(false); } });
      wrap.querySelector('[data-no]').addEventListener('click', () => { settled = true; Modal.close(); resolve(false); });
      wrap.querySelector('[data-yes]').addEventListener('click', () => { settled = true; Modal.close(); resolve(true); });
    });
  }
  window.confirmDialog = confirmDialog;

  function loginPrompt(message) {
    return `<div class="empty-state">
      <h2>${Helpers.escapeHtml(message)}</h2>
      <p>Log in to see videos from creators you follow.</p>
      <a href="#/login" class="btn btn-primary" data-nav>Log in</a>
    </div>`;
  }

  const feedView = {
    async mount(root, params) {
      root.classList.add('view-root--feed');
      const tab = params.tab === 'following' ? 'following' : 'foryou';

      root.innerHTML = `
        <div class="feed-tabs">
          <a href="#/" data-nav class="${tab === 'foryou' ? 'active' : ''}">For You</a>
          <a href="#/following" data-nav class="${tab === 'following' ? 'active' : ''}">Following</a>
        </div>
        <div class="feed-scroll"><div class="loading-row"><div class="loading-spinner"></div></div></div>
      `;
      const scrollEl = root.querySelector('.feed-scroll');

      if (tab === 'following' && !Store.currentUser) {
        scrollEl.innerHTML = loginPrompt("You're not logged in");
        return { unmount() {} };
      }

      let cursor = 0;
      let hasMore = true;
      let loading = false;
      const seenIds = new Set();
      const cards = [];
      let currentCardEl = null;

      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          const card = cards.find((c) => c.el === entry.target);
          if (!card) return;
          if (entry.isIntersecting && entry.intersectionRatio >= 0.6) {
            if (currentCardEl && currentCardEl !== card) currentCardEl.leave();
            currentCardEl = card;
            card.enter();
          } else if (currentCardEl === card && entry.intersectionRatio < 0.35) {
            card.leave();
          }
        });
      }, { root: scrollEl, threshold: [0, 0.35, 0.6] });

      const sentinel = document.createElement('div');
      sentinel.style.height = '1px';
      const sentinelIo = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) loadMore();
      }, { root: scrollEl, threshold: 0.01 });

      function appendVideos(list) {
        list.forEach((video) => {
          if (seenIds.has(video.id)) return;
          seenIds.add(video.id);
          const card = buildCard(video, {
            onRemoved() {
              io.unobserve(card.el);
              const idx = cards.indexOf(card);
              if (idx !== -1) cards.splice(idx, 1);
              if (currentCardEl === card) currentCardEl = null;
            },
          });
          cards.push(card);
          scrollEl.insertBefore(card.el, sentinel);
          io.observe(card.el);
        });
      }

      async function loadMore() {
        if (loading || !hasMore) return;
        loading = true;
        try {
          const res = await Api.feed(tab, cursor, 6);
          cursor = res.nextCursor;
          hasMore = res.hasMore;
          appendVideos(res.items);
          if (!hasMore) {
            const end = Helpers.el(`<div class="feed-endcap"><p>You're all caught up 🎉</p></div>`);
            scrollEl.appendChild(end);
            sentinel.remove();
          }
        } catch (err) {
          Helpers.toast(err.message || 'Failed to load feed');
          hasMore = false;
        } finally {
          loading = false;
        }
      }

      async function init() {
        scrollEl.innerHTML = '';
        scrollEl.appendChild(sentinel);
        sentinelIo.observe(sentinel);

        if (params.focusId) {
          try {
            const { video } = await Api.getVideo(params.focusId);
            appendVideos([video]);
          } catch (e) { /* video may have been deleted; continue with feed */ }
        }
        await loadMore();
        requestAnimationFrame(() => {
          if (cards.length) { cards[0].el.scrollIntoView({ block: 'start' }); }
        });
      }

      function onKeydown(e) {
        if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault();
          const idx = cards.findIndex((c) => c === currentCardEl);
          const nextIdx = e.key === 'ArrowDown' ? idx + 1 : idx - 1;
          if (cards[nextIdx]) cards[nextIdx].el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else if (e.key === ' ') {
          e.preventDefault();
          if (currentCardEl) currentCardEl.el.querySelector('[data-action="toggle-play"]').click();
        }
      }
      window.addEventListener('keydown', onKeydown);

      init();

      return {
        unmount() {
          window.removeEventListener('keydown', onKeydown);
          io.disconnect();
          sentinelIo.disconnect();
          cards.forEach((c) => c.destroy());
        },
      };
    },
  };

  window.Views = window.Views || {};
  window.Views.feed = feedView;
})();
