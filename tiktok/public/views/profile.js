'use strict';
/* Profile page: header, stats, videos/liked tabs, follower/following lists. */

(function () {
  function userRowHtml(u) {
    const authed = !!Store.currentUser;
    const showFollowBtn = authed && !u.isSelf;
    return `
      <div class="user-row" data-username="${u.username}">
        <a href="#/user/${u.username}" data-nav class="avatar">${Helpers.avatarSvg(u.avatarSeed, u.displayName, 48)}</a>
        <div class="user-row-info">
          <div class="user-row-name">
            <a href="#/user/${u.username}" data-nav>@${Helpers.escapeHtml(u.username)}</a>
            ${u.verified ? icon('checkBadge', 14) : ''}
          </div>
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

  function openUserListModal(title, fetchPage) {
    const wrap = Helpers.el(`
      <div class="comments-drawer">
        <div class="comments-header"><h3>${Helpers.escapeHtml(title)}</h3><button class="comments-close">${icon('x', 20)}</button></div>
        <div class="comments-list"><div class="user-list"></div><div class="loading-row" data-role="loader"><div class="loading-spinner"></div></div></div>
      </div>`);
    Modal.open(wrap);
    wrap.querySelector('.comments-close').addEventListener('click', () => Modal.close());
    const listEl = wrap.querySelector('.user-list');
    const loader = wrap.querySelector('[data-role="loader"]');
    let cursor = 0, hasMore = true, loading = false;

    async function loadMore() {
      if (loading || !hasMore) return;
      loading = true;
      try {
        const res = await fetchPage(cursor);
        cursor = res.nextCursor; hasMore = res.hasMore;
        listEl.insertAdjacentHTML('beforeend', res.items.map(userRowHtml).join(''));
        wireFollowButtons(listEl);
        if (!res.items.length && listEl.children.length === 0) {
          listEl.innerHTML = `<div class="comments-empty">Nobody here yet.</div>`;
        }
      } catch (e) {
        Helpers.toast('Failed to load list');
      } finally {
        loading = false;
        loader.style.display = hasMore ? '' : 'none';
      }
    }
    wrap.querySelector('.comments-list').addEventListener('scroll', (e) => {
      const el = e.currentTarget;
      if (el.scrollTop + el.clientHeight > el.scrollHeight - 120) loadMore();
    });
    loadMore();
  }

  function gridCellHtml(video, showDelete) {
    return `
      <div class="grid-cell" data-video-id="${video.id}">
        ${video.type === 'file' ? `<video src="${video.url}" muted loop playsinline preload="metadata"></video>` : `<canvas></canvas>`}
        <div class="grid-caption">${Helpers.escapeHtml(video.caption)}</div>
        <div class="grid-views">${icon('play', 12)} ${Helpers.formatCount(video.stats.views)}</div>
        ${showDelete ? `<button class="grid-delete" data-action="delete-video" data-id="${video.id}">${icon('trash', 14)}</button>` : ''}
      </div>`;
  }

  async function renderTabContent(root, user, tab) {
    const wrap = root.querySelector('.profile-tab-content');
    wrap.innerHTML = `<div class="loading-row"><div class="loading-spinner"></div></div>`;

    if (tab === 'liked' && !user.isSelf) {
      wrap.innerHTML = `<div class="empty-state"><h2>This is private</h2><p>Liked videos are only visible to the account owner.</p></div>`;
      return;
    }

    let cursor = 0, hasMore = true, loading = false;
    const fetcher = tab === 'liked'
      ? (c) => Api.userLiked(user.username, c, 18)
      : (c) => Api.userVideos(user.username, c, 18);

    wrap.innerHTML = `<div class="video-grid"></div><div class="loading-row" data-role="loader" style="display:none"><div class="loading-spinner"></div></div>`;
    const grid = wrap.querySelector('.video-grid');
    const loader = wrap.querySelector('[data-role="loader"]');
    const renderers = [];

    async function loadMore() {
      if (loading || !hasMore) return;
      loading = true;
      loader.style.display = '';
      try {
        const res = await fetcher(cursor);
        cursor = res.nextCursor; hasMore = res.hasMore;
        if (cursor === 0 && res.items.length === 0) {
          grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><h2>${tab === 'liked' ? 'No liked videos yet' : 'No videos yet'}</h2></div>`;
          loader.style.display = 'none';
          return;
        }
        res.items.forEach((video) => {
          const cell = Helpers.el(gridCellHtml(video, tab === 'videos' && user.isSelf));
          grid.appendChild(cell);
          if (video.type === 'procedural') {
            const canvas = cell.querySelector('canvas');
            const r = window.createProceduralVideo(canvas, video.style, video.visualSeed);
            r.start();
            renderers.push(r);
          }
          cell.addEventListener('click', (e) => {
            if (e.target.closest('[data-action="delete-video"]')) return;
            navigate(`#/video/${video.id}`);
          });
          const delBtn = cell.querySelector('[data-action="delete-video"]');
          if (delBtn) {
            delBtn.addEventListener('click', async (e) => {
              e.stopPropagation();
              const ok = await confirmDialog('Delete video?', "This can't be undone.", 'Delete');
              if (!ok) return;
              try {
                await Api.deleteVideo(video.id);
                cell.remove();
                Helpers.toast('Video deleted');
              } catch (err) {
                Helpers.toast(err.message || 'Failed to delete');
              }
            });
          }
        });
      } catch (err) {
        Helpers.toast(err.message || 'Failed to load videos');
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
    await loadMore();
    return () => { root.removeEventListener('scroll', onScroll); renderers.forEach((r) => r.destroy()); };
  }

  const profileView = {
    async mount(root, params) {
      root.classList.add('view-root--page');
      root.innerHTML = `<div class="loading-row"><div class="loading-spinner"></div></div>`;
      let user;
      try {
        ({ user } = await Api.getUser(params.username));
      } catch (e) {
        root.innerHTML = `<div class="empty-state"><h2>User not found</h2><p>@${Helpers.escapeHtml(params.username)} doesn't exist.</p><a href="#/" class="btn btn-primary" data-nav>Go home</a></div>`;
        return { unmount() {} };
      }

      const tab = params.tab === 'liked' ? 'liked' : 'videos';

      root.innerHTML = `
        <div class="profile-page">
          <div class="profile-header">
            <div class="profile-avatar">${Helpers.avatarSvg(user.avatarSeed, user.displayName, 116)}</div>
            <div class="profile-info">
              <div class="profile-username-row">
                <span class="profile-username">@${Helpers.escapeHtml(user.username)}</span>
                ${user.verified ? `<span class="profile-verified">${icon('checkBadge', 20)}</span>` : ''}
              </div>
              <div class="profile-displayname">${Helpers.escapeHtml(user.displayName)}</div>
              <div class="profile-stats">
                <a href="#" data-role="following-link"><span class="stat-num">${Helpers.formatCount(user.following)}</span><span class="stat-label">Following</span></a>
                <a href="#" data-role="followers-link"><span class="stat-num">${Helpers.formatCount(user.followers)}</span><span class="stat-label">Followers</span></a>
                <span><span class="stat-num">${Helpers.formatCount(user.likes)}</span><span class="stat-label">Likes</span></span>
              </div>
              <div class="profile-actions">
                ${user.isSelf
                  ? `<a href="#/settings" data-nav class="btn">${icon('edit', 16)} Edit profile</a>`
                  : `<button class="btn ${user.isFollowing ? 'following' : 'btn-primary'}" id="profile-follow-btn">${user.isFollowing ? 'Following' : 'Follow'}</button>`}
              </div>
              <p class="profile-bio">${Helpers.escapeHtml(user.bio || (user.isSelf ? 'Add a bio in Edit profile.' : ''))}</p>
            </div>
          </div>
          <div class="profile-tabs">
            <a href="#/user/${user.username}" data-nav class="profile-tab ${tab === 'videos' ? 'active' : ''}">${icon('home', 16)} Videos</a>
            ${user.isSelf ? `<a href="#/user/${user.username}/liked" data-nav class="profile-tab ${tab === 'liked' ? 'active' : ''}">${icon('heart', 16)} Liked</a>` : ''}
          </div>
          <div class="profile-tab-content"></div>
        </div>`;

      const followBtn = root.querySelector('#profile-follow-btn');
      if (followBtn) {
        followBtn.addEventListener('click', async () => {
          if (!Store.currentUser) { navigate('#/login'); return; }
          followBtn.disabled = true;
          try {
            const res = await Api.follow(user.username);
            user.isFollowing = res.following;
            followBtn.textContent = res.following ? 'Following' : 'Follow';
            followBtn.classList.toggle('following', res.following);
            followBtn.classList.toggle('btn-primary', !res.following);
            root.querySelector('[data-role="followers-link"] .stat-num').textContent = Helpers.formatCount(res.followers);
          } catch (err) {
            Helpers.toast(err.message || 'Failed to follow');
          } finally {
            followBtn.disabled = false;
          }
        });
      }

      root.querySelector('[data-role="following-link"]').addEventListener('click', (e) => {
        e.preventDefault();
        openUserListModal(`Following`, (cursor) => Api.userFollowing(user.username, cursor, 20));
      });
      root.querySelector('[data-role="followers-link"]').addEventListener('click', (e) => {
        e.preventDefault();
        openUserListModal(`Followers`, (cursor) => Api.userFollowers(user.username, cursor, 20));
      });

      const cleanupTab = await renderTabContent(root, user, tab);

      return { unmount() { if (typeof cleanupTab === 'function') cleanupTab(); } };
    },
  };

  window.Views = window.Views || {};
  window.Views.profile = profileView;
})();
