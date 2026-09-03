'use strict';
/* Notifications / inbox page. */

(function () {
  const TYPE_ICON = { follow: 'users', like: 'heartFilled', comment: 'comment', reply: 'comment' };

  function notifRowHtml(n) {
    return `
      <div class="notif-row ${n.read ? '' : 'unread'}" data-type="${n.type}" data-username="${n.actor.username}" ${n.video ? `data-video-id="${n.video.id}"` : ''}>
        <a href="#/user/${n.actor.username}" data-nav class="avatar notif-icon-badge">
          ${Helpers.avatarSvg(n.actor.avatarSeed, n.actor.displayName, 44)}
          <span class="badge-emoji">${icon(TYPE_ICON[n.type] || 'bell', 11)}</span>
        </a>
        <div class="notif-text">
          <div><b><a href="#/user/${n.actor.username}" data-nav>${Helpers.escapeHtml(n.actor.displayName)}</a></b> ${Helpers.escapeHtml(n.text)}${n.commentText ? `: "${Helpers.escapeHtml(n.commentText)}"` : ''}</div>
          <div class="notif-time">${Helpers.timeAgo(n.createdAt)}</div>
        </div>
        ${n.video ? `<div class="notif-thumb" data-video-thumb>${n.video.style ? '<canvas></canvas>' : icon('play', 18)}</div>` : ''}
      </div>`;
  }

  const notificationsView = {
    async mount(root) {
      root.classList.add('view-root--page');
      root.innerHTML = `
        <div class="notif-page">
          <h1>Notifications</h1>
          <div id="notif-list"><div class="loading-row"><div class="loading-spinner"></div></div></div>
        </div>`;
      const listEl = root.querySelector('#notif-list');
      const renderers = [];

      try {
        const { notifications } = await Api.notifications();
        if (!notifications.length) {
          listEl.innerHTML = `<div class="empty-state"><h2>No notifications yet</h2><p>Likes, comments and new followers will show up here.</p></div>`;
        } else {
          listEl.innerHTML = notifications.map(notifRowHtml).join('');
          // Notification rows render in the same order as `notifications`, and
          // only entries with a styled video get a <canvas> thumb -- so the
          // Nth canvas in the DOM lines up with the Nth video-style notification.
          const thumbCanvases = listEl.querySelectorAll('.notif-thumb canvas');
          const videoNotifs = notifications.filter((n) => n.video && n.video.style);
          thumbCanvases.forEach((canvas, i) => {
            const n = videoNotifs[i];
            if (!n) return;
            const r = window.createProceduralVideo(canvas, n.video.style, n.video.visualSeed);
            r.start();
            renderers.push(r);
          });
          listEl.addEventListener('click', (e) => {
            const row = e.target.closest('.notif-row');
            if (!row) return;
            if (e.target.closest('a[data-nav]')) return; // let inner links behave normally
            if (row.dataset.videoId) navigate(`#/video/${row.dataset.videoId}`);
            else navigate(`#/user/${row.dataset.username}`);
          });
        }
        Store.unreadNotifications = 0;
        Store.emit();
        Api.readAllNotifications().catch(() => {});
      } catch (e) {
        listEl.innerHTML = `<div class="empty-state"><h2>Couldn't load notifications</h2></div>`;
      }

      return { unmount() { renderers.forEach((r) => r.destroy()); } };
    },
  };

  window.Views = window.Views || {};
  window.Views.notifications = notificationsView;
})();
