'use strict';
/* Login/register and edit-profile ("settings") views. */

(function () {
  const authView = {
    async mount(root) {
      root.classList.add('view-root--page');
      if (Store.currentUser) {
        navigate(`#/user/${Store.currentUser.username}`);
        return { unmount() {} };
      }
      let mode = 'login';

      function render() {
        root.innerHTML = `
          <div class="auth-page">
            <div class="auth-card">
              <h1>${mode === 'login' ? 'Log in' : 'Sign up'}</h1>
              <div class="auth-demo-hint">Demo account: username <b>chefmarco</b>, password <b>password123</b> (any seed creator works, all share that password) &mdash; or sign up as a new user.</div>
              <form id="auth-form">
                ${mode === 'register' ? `
                <div class="field">
                  <label for="f-display">Display name</label>
                  <input id="f-display" type="text" maxlength="40" placeholder="Your name">
                </div>` : ''}
                <div class="field">
                  <label for="f-username">Username</label>
                  <input id="f-username" type="text" maxlength="24" autocomplete="username" placeholder="username" required>
                  ${mode === 'register' ? '<span class="field-hint">2-24 characters: letters, numbers, "." or "_"</span>' : ''}
                </div>
                <div class="field">
                  <label for="f-password">Password</label>
                  <input id="f-password" type="password" autocomplete="${mode === 'login' ? 'current-password' : 'new-password'}" placeholder="Password" required>
                  ${mode === 'register' ? '<span class="field-hint">At least 6 characters</span>' : ''}
                </div>
                <div class="field-error" id="auth-error"></div>
                <button type="submit" class="btn btn-primary btn-block" id="auth-submit">${mode === 'login' ? 'Log in' : 'Sign up'}</button>
              </form>
              <div class="auth-switch">
                ${mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
                <button type="button" id="auth-toggle">${mode === 'login' ? 'Sign up' : 'Log in'}</button>
              </div>
            </div>
          </div>`;

        root.querySelector('#auth-toggle').addEventListener('click', () => { mode = mode === 'login' ? 'register' : 'login'; render(); });

        root.querySelector('#auth-form').addEventListener('submit', async (e) => {
          e.preventDefault();
          const username = root.querySelector('#f-username').value.trim();
          const password = root.querySelector('#f-password').value;
          const errorEl = root.querySelector('#auth-error');
          const submitBtn = root.querySelector('#auth-submit');
          errorEl.textContent = '';
          submitBtn.disabled = true;
          try {
            const result = mode === 'login'
              ? await Api.login(username, password)
              : await Api.register(username, password, root.querySelector('#f-display').value.trim());
            Store.setUser(result.user);
            Helpers.toast(mode === 'login' ? `Welcome back, @${result.user.username}` : `Welcome to TikTok, @${result.user.username}`);
            const redirect = Store.afterLoginRedirect || `#/user/${result.user.username}`;
            Store.afterLoginRedirect = null;
            navigate(redirect);
          } catch (err) {
            errorEl.textContent = err.message || 'Something went wrong.';
            submitBtn.disabled = false;
          }
        });
      }

      render();
      return { unmount() {} };
    },
  };

  const AVATAR_COUNT = 14;

  const settingsView = {
    async mount(root) {
      root.classList.add('view-root--page');
      const user = Store.currentUser;
      let chosenSeed = user.avatarSeed;

      root.innerHTML = `
        <div class="auth-page">
          <div class="auth-card" style="max-width:460px">
            <h1>Edit profile</h1>
            <form id="settings-form">
              <div class="field">
                <label>Avatar</label>
                <div id="avatar-picker" style="display:flex;flex-wrap:wrap;gap:10px"></div>
              </div>
              <div class="field">
                <label for="s-display">Display name</label>
                <input id="s-display" type="text" maxlength="40" value="${Helpers.escapeHtml(user.displayName)}">
              </div>
              <div class="field">
                <label for="s-bio">Bio</label>
                <textarea id="s-bio" maxlength="160">${Helpers.escapeHtml(user.bio || '')}</textarea>
                <div class="char-count"><span id="s-bio-count">${(user.bio || '').length}</span>/160</div>
              </div>
              <div class="field-error" id="settings-error"></div>
              <div class="upload-actions">
                <a href="#/user/${user.username}" data-nav class="btn">Cancel</a>
                <button type="submit" class="btn btn-primary" id="settings-submit">Save</button>
              </div>
            </form>
          </div>
        </div>`;

      const picker = root.querySelector('#avatar-picker');
      function renderPicker() {
        picker.innerHTML = new Array(AVATAR_COUNT).fill(0).map((_, i) => {
          const seed = i + 1;
          return `<button type="button" data-seed="${seed}" style="width:44px;height:44px;border-radius:50%;overflow:hidden;border:2px solid ${seed === chosenSeed ? 'var(--accent-2)' : 'transparent'};padding:0">${Helpers.avatarSvg(seed, user.displayName, 44)}</button>`;
        }).join('');
        picker.querySelectorAll('button').forEach((btn) => {
          btn.addEventListener('click', () => { chosenSeed = parseInt(btn.dataset.seed, 10); renderPicker(); });
        });
      }
      renderPicker();

      root.querySelector('#s-bio').addEventListener('input', (e) => {
        root.querySelector('#s-bio-count').textContent = e.target.value.length;
      });

      root.querySelector('#settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const errorEl = root.querySelector('#settings-error');
        const submitBtn = root.querySelector('#settings-submit');
        errorEl.textContent = '';
        submitBtn.disabled = true;
        try {
          const { user: updated } = await Api.updateMe({
            displayName: root.querySelector('#s-display').value.trim(),
            bio: root.querySelector('#s-bio').value,
            avatarSeed: chosenSeed,
          });
          Store.setUser(updated);
          Helpers.toast('Profile updated');
          navigate(`#/user/${updated.username}`);
        } catch (err) {
          errorEl.textContent = err.message || 'Something went wrong.';
          submitBtn.disabled = false;
        }
      });

      return { unmount() {} };
    },
  };

  window.Views = window.Views || {};
  window.Views.auth = authView;
  window.Views.settings = settingsView;
})();
