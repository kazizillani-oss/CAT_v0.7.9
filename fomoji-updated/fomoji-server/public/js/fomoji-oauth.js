/* ==========================================================================
   FOMOJI — OAuth provider buttons. Populates #oauthProviderList from
   /api/oauth/providers (real config check, not hard-coded) and, since each
   button is a plain link to /api/oauth/<provider>/start, clicking one does
   a genuine top-level redirect into the provider's real consent screen.
   Unconfigured providers link straight to oauth-config.html to configure.
   ========================================================================== */
(function () {
  const ICONS = {
    google: '🌐',
    apple: '🍎',
    microsoft: '🪟',
    github: '🐙',
    facebook: '🔷',
  };

  async function renderProviderList() {
    const list = document.getElementById('oauthProviderList');
    if (!list) return;
    list.innerHTML = '';
    let providers;
    try {
      const res = await fetch('/api/oauth/providers');
      ({ providers } = await res.json());
    } catch {
      return; // backend unreachable
    }

    Object.entries(providers).forEach(([key, info]) => {
      const el = document.createElement('a');
      el.className = 'btn btn-ghost';
      el.style.cssText = 'justify-content:center; text-decoration:none; margin-bottom:4px;';
      const icon = ICONS[key] ? `${ICONS[key]} ` : '';
      if (info.configured) {
        el.href = `/api/oauth/${key}/start`;
        el.innerHTML = `<span class="btn-label">${icon}Sign in with ${info.label}</span>`;
      } else {
        el.href = `oauth-config.html#${key}`;
        el.style.opacity = '0.75';
        el.title = `${info.label} authentication is not configured yet. Click to configure.`;
        el.innerHTML = `<span class="btn-label">${icon}Sign in with ${info.label} <small style="opacity:0.6;">(click to setup)</small></span>`;
      }
      list.appendChild(el);
    });

    // Provide explicit configuration link
    const cfgLink = document.createElement('a');
    cfgLink.href = 'oauth-config.html';
    cfgLink.className = 'btn btn-ghost';
    cfgLink.style.cssText = 'justify-content:center; text-decoration:none; font-size:12px; opacity:0.8; border:1px dashed var(--line); margin-top:4px;';
    cfgLink.innerHTML = '<span class="btn-label">⚙ Configure Providers (Google, GitHub, Microsoft, Facebook, Apple)</span>';
    list.appendChild(cfgLink);
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
      alertBox.textContent = `An account with that email already exists. Sign in with your existing method, then add ${linkNeeded} from Security → Connected Login Methods.`;
      alertBox.style.display = 'block';
    }
  }

  renderProviderList();
  showQueryMessages();
})();
