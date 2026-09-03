'use strict';
/* Search / discover, hashtag pages, and sound pages. */

(function () {
  function gridCellHtml(video) {
    return `
      <div class="grid-cell" data-video-id="${video.id}">
        ${video.type === 'file' ? `<video src="${video.url}" muted loop playsinline preload="metadata"></video>` : `<canvas></canvas>`}
        <div class="grid-caption">${Helpers.escapeHtml(video.caption)}</div>
        <div class="grid-views">${icon('play', 12)} ${Helpers.formatCount(video.stats.views)}</div>
      </div>`;
  }

  function mountVideoGrid(root, container, fetchPage) {
    let cursor = 0, hasMore = true, loading = false;
    const renderers = [];
    container.innerHTML = `<div class="video-grid"></div><div class="loading-row" data-role="loader" style="display:none"><div class="loading-spinner"></div></div>`;
    const grid = container.querySelector('.video-grid');
    const loader = container.querySelector('[data-role="loader"]');

    async function loadMore() {
      if (loading || !hasMore) return;
      loading = true;
      loader.style.display = '';
      try {
        const res = await fetchPage(cursor);
        const wasFirstPage = cursor === 0;
        cursor = res.nextCursor; hasMore = res.hasMore;
        if (wasFirstPage && res.items.length === 0) {
          grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><h2>No videos yet</h2></div>`;
        }
        res.items.forEach((video) => {
          const cell = Helpers.el(gridCellHtml(video));
          grid.appendChild(cell);
          if (video.type === 'procedural') {
            const canvas = cell.querySelector('canvas');
            const r = window.createProceduralVideo(canvas, video.style, video.visualSeed);
            r.start();
            renderers.push(r);
          }
          cell.addEventListener('click', () => navigate(`#/video/${video.id}`));
        });
      } catch (e) {
        Helpers.toast('Failed to load videos');
        hasMore = false;
      } finally {
        loading = false;
        loader.style.display = hasMore ? '' : 'none';
      }
    }

    function onScroll() {
      if (root.scrollTop + root.clientHeight > root.scrollHeight - 400) loadMore();
    }
    root.addEventListener('scroll', onScroll);
    loadMore();
    return () => { root.removeEventListener('scroll', onScroll); renderers.forEach((r) => r.destroy()); };
  }

  function userRowHtml(u) {
    const authed = !!Store.currentUser;
    const showFollowBtn = authed && !u.isSelf;
    return `
      <div class="user-row">
        <a href="#/user/${u.username}" data-nav class="avatar">${Helpers.avatarSvg(u.avatarSeed, u.displayName, 48)}</a>
        <div class="user-row-info">
          <div class="user-row-name"><a href="#/user/${u.username}" data-nav>@${Helpers.escapeHtml(u.username)}</a>${u.verified ? icon('checkBadge', 14) : ''}</div>
          <div class="user-row-sub">${Helpers.escapeHtml(u.displayName)} &middot; ${Helpers.formatCount(u.followers)} followers</div>
        </div>
        ${showFollowBtn ? `<button class="btn btn-sm ${u.isFollowing ? 'following' : 'btn-primary'}" data-action="follow" data-username="${u.username}">${u.isFollowing ? 'Following' : 'Follow'}</button>` : ''}
      </div>`;
  }

  function wireFollowButtons(container) {
    container.querySelectorAll('[data-action="follow"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!Store.currentUser) { navigate('#/login'); return; }
        btn.disabled = true;
        try {
          const res = await Api.follow(btn.dataset.username);
          btn.textContent = res.following ? 'Following' : 'Follow';
          btn.classList.toggle('following', res.following);
          btn.classList.toggle('btn-primary', !res.following);
        } catch (err) {
          Helpers.toast(err.message || 'Failed to follow');
        } finally {
          btn.disabled = false;
        }
      });
    });
  }

  function discoverHtml(data) {
    return `
      ${data.suggestedUsers.length ? `
      <div class="discover-section">
        <h3>Suggested accounts</h3>
        <div class="user-list">${data.suggestedUsers.slice(0, 6).map(userRowHtml).join('')}</div>
      </div>` : ''}
      ${data.trendingHashtags.length ? `
      <div class="discover-section">
        <h3>Trending hashtags</h3>
        <div class="hashtag-chip-row">${data.trendingHashtags.map((h) => `<a href="#/tag/${h.tag}" data-nav class="hashtag-chip">#${Helpers.escapeHtml(h.tag)} <span class="field-hint">${Helpers.formatCount(h.count)}</span></a>`).join('')}</div>
      </div>` : ''}
      ${data.trendingSounds.length ? `
      <div class="discover-section">
        <h3>Trending sounds</h3>
        <div class="sound-chip-row">${data.trendingSounds.map((s) => `<a href="#/sound/${s.id}" data-nav class="sound-chip"><span class="action-sound-disc">${icon('music', 12)}</span>${Helpers.escapeHtml(s.name)}</a>`).join('')}</div>
      </div>` : ''}
      <div class="discover-section">
        <h3>Videos for you</h3>
        <div id="discover-grid"></div>
      </div>
    `;
  }

  function searchResultsHtml(data) {
    const noResults = !data.users.length && !data.videos.length && !data.sounds.length;
    if (noResults) {
      return `<div class="empty-state"><h2>No results for "${Helpers.escapeHtml(data.query)}"</h2><p>Try a different search term.</p></div>`;
    }
    return `
      ${data.users.length ? `<div class="discover-section"><h3>Accounts</h3><div class="user-list">${data.users.map(userRowHtml).join('')}</div></div>` : ''}
      ${data.sounds.length ? `<div class="discover-section"><h3>Sounds</h3><div class="sound-chip-row">${data.sounds.map((s) => `<a href="#/sound/${s.id}" data-nav class="sound-chip"><span class="action-sound-disc">${icon('music', 12)}</span>${Helpers.escapeHtml(s.name)}</a>`).join('')}</div></div>` : ''}
      ${data.videos.length ? `<div class="discover-section"><h3>Videos</h3><div class="video-grid">${data.videos.map(gridCellHtml).join('')}</div></div>` : ''}
    `;
  }

  const searchView = {
    async mount(root, params, query) {
      root.classList.add('view-root--page');
      root.innerHTML = `
        <div class="search-page">
          <form id="search-form" style="margin-bottom:18px">
            <div class="sidebar-search" style="margin:0">
              <span class="sidebar-search-icon">${icon('search', 18)}</span>
              <input type="search" id="search-input" placeholder="Search accounts, sounds, hashtags..." autocomplete="off" value="${Helpers.escapeHtml(query.q || '')}">
            </div>
          </form>
          <div id="search-results"><div class="loading-row"><div class="loading-spinner"></div></div></div>
        </div>`;

      const input = root.querySelector('#search-input');
      const resultsEl = root.querySelector('#search-results');
      let renderers = [];
      let scrollCleanup = null;

      function clearRenderers() {
        renderers.forEach((r) => r.destroy());
        renderers = [];
        if (scrollCleanup) { scrollCleanup(); scrollCleanup = null; }
      }

      async function runSearch(q) {
        clearRenderers();
        resultsEl.innerHTML = `<div class="loading-row"><div class="loading-spinner"></div></div>`;
        try {
          const data = await Api.search(q);
          const hash = `#/search${q ? '?q=' + encodeURIComponent(q) : ''}`;
          if (location.hash !== hash) history.replaceState(null, '', hash);

          if (!q) {
            resultsEl.innerHTML = discoverHtml(data);
            wireFollowButtons(resultsEl);
            const gridWrap = resultsEl.querySelector('#discover-grid');
            let served = false;
            scrollCleanup = mountVideoGrid(root, gridWrap, async () => {
              if (served) return { items: [], nextCursor: 0, hasMore: false };
              served = true;
              return { items: data.videos, nextCursor: data.videos.length, hasMore: false };
            });
          } else {
            resultsEl.innerHTML = searchResultsHtml(data);
            wireFollowButtons(resultsEl);
            data.videos.forEach((video) => {
              const cell = [...resultsEl.querySelectorAll('.grid-cell')].find((c) => c.dataset.videoId === video.id);
              if (!cell) return;
              cell.addEventListener('click', () => navigate(`#/video/${video.id}`));
              if (video.type === 'procedural') {
                const canvas = cell.querySelector('canvas');
                const r = window.createProceduralVideo(canvas, video.style, video.visualSeed);
                r.start();
                renderers.push(r);
              }
            });
          }
        } catch (e) {
          resultsEl.innerHTML = `<div class="empty-state"><h2>Search failed</h2><p>${Helpers.escapeHtml(e.message || '')}</p></div>`;
        }
      }

      const debouncedSearch = Helpers.debounce((q) => runSearch(q), 350);
      input.addEventListener('input', () => debouncedSearch(input.value.trim()));
      root.querySelector('#search-form').addEventListener('submit', (e) => {
        e.preventDefault();
        runSearch(input.value.trim());
      });

      await runSearch((query.q || '').trim());

      return { unmount() { clearRenderers(); } };
    },
  };

  const tagView = {
    async mount(root, params) {
      root.classList.add('view-root--page');
      root.innerHTML = `
        <div class="collection-header">
          <h1><span class="collection-icon">${icon('search', 24)}</span>#${Helpers.escapeHtml(params.tag)}</h1>
          <p class="collection-sub" id="tag-count">Loading videos&hellip;</p>
        </div>
        <div class="collection-grid-wrap" id="tag-grid"></div>`;
      const gridWrap = root.querySelector('#tag-grid');
      const countEl = root.querySelector('#tag-count');
      let first = true;
      const cleanup = mountVideoGrid(root, gridWrap, async (cursor) => {
        const res = await Api.tagVideos(params.tag, cursor, 18);
        if (first) { first = false; countEl.textContent = `${Helpers.formatCount(res.total)} video${res.total === 1 ? '' : 's'}`; }
        return res;
      });
      return { unmount() { cleanup(); } };
    },
  };

  const soundView = {
    async mount(root, params) {
      root.classList.add('view-root--page');
      root.innerHTML = `<div class="loading-row"><div class="loading-spinner"></div></div>`;
      let sound;
      try {
        ({ sound } = await Api.sound(params.id));
      } catch (e) {
        root.innerHTML = `<div class="empty-state"><h2>Sound not found</h2><a href="#/" class="btn btn-primary" data-nav>Go home</a></div>`;
        return { unmount() {} };
      }
      root.innerHTML = `
        <div class="collection-header">
          <h1><span class="collection-icon">${icon('music', 24)}</span>${Helpers.escapeHtml(sound.name)}</h1>
          <p class="collection-sub">${Helpers.formatCount(sound.uses)} videos</p>
        </div>
        <div class="collection-grid-wrap" id="sound-grid"></div>`;
      const gridWrap = root.querySelector('#sound-grid');
      const cleanup = mountVideoGrid(root, gridWrap, (cursor) => Api.soundVideos(params.id, cursor, 18));
      return { unmount() { cleanup(); } };
    },
  };

  window.Views = window.Views || {};
  window.Views.search = searchView;
  window.Views.tag = tagView;
  window.Views.sound = soundView;
})();
