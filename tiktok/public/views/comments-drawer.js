'use strict';
/* Slide-up comments drawer, opened from the feed action rail (or a grid cell). */

function commentRowHtml(c, isReply) {
  const authed = !!Store.currentUser;
  return `
    <div class="comment-row" data-comment-id="${c.id}">
      <a href="#/user/${c.author.username}" data-nav class="avatar" style="width:${isReply ? 28 : 34}px;height:${isReply ? 28 : 34}px">${Helpers.avatarSvg(c.author.avatarSeed, c.author.displayName, isReply ? 28 : 34)}</a>
      <div class="comment-body">
        <div class="comment-author">
          <a href="#/user/${c.author.username}" data-nav>${Helpers.escapeHtml(c.author.displayName)}</a>
        </div>
        <div class="comment-text">${Helpers.escapeHtml(c.text)}</div>
        <div class="comment-meta">
          <span>${Helpers.timeAgo(c.createdAt)}</span>
          <button class="comment-like-btn ${c.isLiked ? 'liked' : ''}" data-action="like-comment" data-id="${c.id}">
            ${icon(c.isLiked ? 'heartFilled' : 'heart', 14)} <span class="like-count">${c.likes > 0 ? Helpers.formatCount(c.likes) : ''}</span>
          </button>
          ${!isReply && authed ? `<button data-action="reply" data-id="${c.id}" data-name="${Helpers.escapeHtml(c.author.displayName)}">Reply</button>` : ''}
          ${c.isOwn ? `<button data-action="delete-comment" data-id="${c.id}">Delete</button>` : ''}
        </div>
        ${!isReply && c.replies && c.replies.length ? `<div class="comment-replies">${c.replies.map((r) => commentRowHtml(r, true)).join('')}</div>` : ''}
      </div>
    </div>`;
}

function openCommentsDrawer(video, onCountChange) {
  const authed = !!Store.currentUser;
  const wrap = Helpers.el(`
    <div class="comments-drawer">
      <div class="comments-header">
        <h3 id="comments-title">Comments</h3>
        <button class="comments-close" aria-label="Close">${icon('x', 22)}</button>
      </div>
      <div class="comments-list"><div class="section-loading"><div class="loading-spinner"></div></div></div>
      <div id="reply-pill-slot"></div>
      <form class="comments-composer">
        <a href="#/user/${Store.currentUser ? Store.currentUser.username : ''}" data-nav class="avatar" style="width:32px;height:32px">${Store.currentUser ? Helpers.avatarSvg(Store.currentUser.avatarSeed, Store.currentUser.displayName, 32) : ''}</a>
        <input type="text" placeholder="${authed ? 'Add comment...' : 'Log in to comment'}" maxlength="300" ${authed ? '' : 'disabled'}>
        <button type="submit" disabled>${icon('send', 20)}</button>
      </form>
    </div>`);

  const backdrop = Modal.open(wrap);
  wrap.querySelector('.comments-close').addEventListener('click', () => Modal.close());

  const listEl = wrap.querySelector('.comments-list');
  const titleEl = wrap.querySelector('#comments-title');
  const input = wrap.querySelector('input');
  const submitBtn = wrap.querySelector('button[type="submit"]');
  const replyPillSlot = wrap.querySelector('#reply-pill-slot');
  let replyTarget = null; // { id, name }
  let total = video.stats.comments;

  input.addEventListener('input', () => { submitBtn.disabled = !input.value.trim(); });

  function setReplyTarget(target) {
    replyTarget = target;
    if (!target) { replyPillSlot.innerHTML = ''; input.placeholder = authed ? 'Add comment...' : 'Log in to comment'; return; }
    input.placeholder = `Reply to ${target.name}`;
    input.focus();
    replyPillSlot.innerHTML = `<div class="reply-target-pill"><span>Replying to ${Helpers.escapeHtml(target.name)}</span><button type="button">${icon('x', 14)}</button></div>`;
    replyPillSlot.querySelector('button').addEventListener('click', () => setReplyTarget(null));
  }

  async function load() {
    try {
      const { comments, total: t } = await Api.comments(video.id);
      total = t;
      titleEl.textContent = total > 0 ? `${Helpers.formatCount(total)} comments` : 'Comments';
      if (!comments.length) {
        listEl.innerHTML = `<div class="comments-empty">No comments yet.<br>Be the first to say something.</div>`;
        return;
      }
      listEl.innerHTML = comments.map((c) => commentRowHtml(c, false)).join('');
    } catch (e) {
      listEl.innerHTML = `<div class="comments-empty">Couldn't load comments.</div>`;
    }
  }

  listEl.addEventListener('click', async (e) => {
    const likeBtn = e.target.closest('[data-action="like-comment"]');
    const replyBtn = e.target.closest('[data-action="reply"]');
    const delBtn = e.target.closest('[data-action="delete-comment"]');
    if (likeBtn) {
      if (!Store.currentUser) { Helpers.toast('Log in to like comments'); navigate('#/login'); return; }
      const id = likeBtn.dataset.id;
      const wasLiked = likeBtn.classList.contains('liked');
      likeBtn.classList.toggle('liked');
      const countSpan = likeBtn.querySelector('.like-count');
      const current = parseInt(countSpan.textContent.replace(/[^\d]/g, ''), 10) || 0;
      const next = wasLiked ? current - 1 : current + 1;
      countSpan.textContent = next > 0 ? Helpers.formatCount(next) : '';
      try {
        const res = await Api.likeComment(id);
        countSpan.textContent = res.likes > 0 ? Helpers.formatCount(res.likes) : '';
        likeBtn.classList.toggle('liked', res.liked);
      } catch (err) {
        likeBtn.classList.toggle('liked', wasLiked);
        countSpan.textContent = current > 0 ? Helpers.formatCount(current) : '';
        Helpers.toast(err.message || 'Failed to like comment');
      }
    } else if (replyBtn) {
      setReplyTarget({ id: replyBtn.dataset.id, name: replyBtn.dataset.name });
    } else if (delBtn) {
      if (!confirm('Delete this comment?')) return;
      try {
        await Api.deleteComment(delBtn.dataset.id);
        await load();
        total = Math.max(0, total - 1);
        if (onCountChange) onCountChange(total);
        Helpers.toast('Comment deleted');
      } catch (err) {
        Helpers.toast(err.message || 'Failed to delete comment');
      }
    }
  });

  wrap.querySelector('.comments-composer').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    if (!Store.currentUser) { Helpers.toast('Log in to comment'); navigate('#/login'); return; }
    submitBtn.disabled = true;
    try {
      await Api.addComment(video.id, text, replyTarget ? replyTarget.id : null);
      input.value = '';
      setReplyTarget(null);
      await load();
      total += 1;
      if (onCountChange) onCountChange(total);
    } catch (err) {
      Helpers.toast(err.message || 'Failed to post comment');
    } finally {
      submitBtn.disabled = !input.value.trim();
    }
  });

  load();
  return backdrop;
}

window.openCommentsDrawer = openCommentsDrawer;
