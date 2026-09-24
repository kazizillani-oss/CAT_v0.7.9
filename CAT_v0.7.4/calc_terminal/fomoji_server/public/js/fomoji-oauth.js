/* ==========================================================================
   FOMOJI — OAuth provider buttons. Populates #oauthProviderList from
   /api/oauth/providers (real config check, not hard-coded) and, since each
   button is a plain link to /api/oauth/<provider>/start, clicking one does
   a genuine top-level redirect into the provider's real consent screen —
   no fetch/JS in the middle of the ceremony itself.
   ========================================================================== */
(function () {
  const ICONS = { google: '🔵', apple: '', microsoft: '🪟', github: '🐙', facebook: '🔷' };

  async function renderProviderList() {
    const list = document.getElementById('oauthProviderList');
    if (!list) return;
    let providers;
    try {
      const res = await fetch('/api/oauth/providers');
      ({ providers } = await res.json());
    } catch {
      return; // backend unreachable — leave the list empty rather than error
    }

    Object.entries(providers).forEach(([key, info]) => {
      const el = document.createElement(info.configured ? 'a' : 'button');
      el.className = 'btn btn-ghost';
      el.style.cssText = 'justify-content:center; text-decoration:none;';
      if (info.configured) {
        el.href = `/api/oauth/${key}/start`;
      } else {
        el.type = 'button';
        el.disabled = true;
        el.title = `${info.label} sign-in is not configured on this server yet.`;
      }
      const icon = ICONS[key] ? `${ICONS[key]} ` : '';
      el.innerHTML = `<span class="btn-label">${icon}Continue with ${info.label}${info.configured ? '' : ' (not configured)'}</span>`;
      list.appendChild(el);
    });
  }

  function showQueryMessages() {
    const params = new URLSearchParams(window.location.search);
    const alertBox = document.getElementById('oauthAlert');
    if (!alertBox) return;

    const oauthError = params.get('oauthError');
    const linkNeeded = params.get('linkNeeded');
    if (oauthError) {
      alertBox.textContent = `Sign-in with that provider didn't complete. Please try again.`;
      alertBox.style.display = 'block';
    } else if (linkNeeded) {
      alertBox.textContent = `An account with that email already exists. Sign in with your existing method, then add ${linkNeeded} from Security \u2192 Connected Login Methods.`;
      alertBox.style.display = 'block';
    }
  }

  renderProviderList();
  showQueryMessages();
})();
