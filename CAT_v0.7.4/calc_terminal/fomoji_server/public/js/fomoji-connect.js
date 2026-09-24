/* ==========================================================================
   FOMOJI — shared "Connect CAT" consent modal
   One implementation, injected into whichever page calls it (home,
   settings, wherever else needs it later) so the flow behaves identically
   everywhere instead of being copy-pasted per page.
   ========================================================================== */

const FomojiConnect = (() => {
  let lastFocused = null;

  const CAT_ASCII = [
    ' \u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557',
    '\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d',
    '\u2588\u2588\u2551     \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551   \u2588\u2588\u2551   ',
    '\u2588\u2588\u2551     \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551   \u2588\u2588\u2551   ',
    '\u255a\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2551  \u2588\u2588\u2551   \u2588\u2588\u2551   ',
    ' \u255a\u2550\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d   \u255a\u2550\u255d   ',
  ];

  function asciiHtml(large) {
    const lines = CAT_ASCII.map(l => `<span class="ascii-line">${l}</span>`).join('\n');
    return `<div class="ascii-cat-wrap"><pre class="ascii-cat${large ? ' is-large' : ''}" aria-hidden="true">${lines}<span class="ascii-cursor">\u2588</span></pre></div>`;
  }

  function ensureModal() {
    let modal = document.getElementById('catModal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'catModal';
    modal.className = 'modal-overlay';
    modal.setAttribute('role', 'presentation');
    modal.innerHTML = `
      <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="catModalTitle" aria-describedby="catModalBody">
        ${asciiHtml(false)}
        <div class="modal-title" id="catModalTitle">Connect CAT CLI</div>
        <p class="modal-body" id="catModalBody">
          <strong>CAT</strong> is requesting to sign in using your Fomoji identity. You'd normally be redirected to CAT CLI to finish pairing.
        </p>
        <div class="modal-scope">
          <div>Verify it's really you (username, no password shared)</div>
          <div>Authenticate future CAT sign-ins with one tap</div>
        </div>
        <p class="field-hint" id="catModalGuestNote" style="margin-top:12px; display:none;">
          You're browsing as a guest — this authorization lives with this guest session and disappears when it ends. Create an account to keep it.
        </p>
        <p class="field-hint" style="margin-top:12px;">
          For a real, non-guest identity this creates an actual server-side connection (Security &rarr; Connections shows it). CAT itself doesn't call this modal yet — it pairs via the separate device-code flow in connector.py/connector.html — so this is the manual equivalent, not a live hand-off.
        </p>
        <div class="modal-actions">
          <button type="button" class="btn btn-ghost" data-cat-cancel>Cancel</button>
          <button type="button" class="btn btn-primary" data-cat-allow>
            <span class="spinner"></span>
            <span class="btn-label">Always Allow</span>
          </button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    return modal;
  }

  function close(modal) {
    modal.classList.remove('is-open');
    if (modal._escHandler) document.removeEventListener('keydown', modal._escHandler);
    if (lastFocused) lastFocused.focus();
  }

  function replayAsciiAnimation(modal) {
    // re-trigger the line-by-line reveal each time the modal opens, not
    // just once on first creation
    modal.querySelectorAll('.ascii-line').forEach(el => {
      el.style.animation = 'none';
      void el.offsetWidth; // force reflow so the animation restarts
      el.style.animation = '';
    });
  }

  /* open(account, { onConnected }) — works for both real accounts and
     guest sessions. Guests get a real, working connection; it's just
     scoped to their session instead of a permanent account (see
     FomojiAPI.connectApp). Only a genuinely missing identity (no account
     at all) is rejected. */
  function open(account, { onConnected } = {}) {
    if (!account) return;
    if (!account.isGuest && !account.id) return;

    const modal = ensureModal();
    const allowBtn = modal.querySelector('[data-cat-allow]');
    const cancelBtn = modal.querySelector('[data-cat-cancel]');
    const guestNote = modal.querySelector('#catModalGuestNote');
    guestNote.style.display = account.isGuest ? 'block' : 'none';

    replayAsciiAnimation(modal);

    lastFocused = document.activeElement;
    modal.classList.add('is-open');
    allowBtn.focus();

    const escHandler = (e) => { if (e.key === 'Escape') close(modal); };
    modal._escHandler = escHandler;
    document.addEventListener('keydown', escHandler);

    modal.addEventListener('click', function overlayClick(e) {
      if (e.target === modal) { close(modal); modal.removeEventListener('click', overlayClick); }
    });

    cancelBtn.onclick = () => close(modal);

    allowBtn.onclick = async () => {
      allowBtn.disabled = true;
      allowBtn.classList.add('is-loading');
      allowBtn.querySelector('.btn-label').textContent = 'Connecting…';
      try {
        // Always redirect to connector.html for the device-code entry flow.
        // This is the standard path: user enters the code shown by CAT CLI
        // on the connector page, then approves it there.
        close(modal);
        window.location.href = '/connector.html';
        return;
      } catch (err) {
        window.FomojiCompanion?.react('error');
        alert(err.message);
      } finally {
        allowBtn.disabled = false;
        allowBtn.classList.remove('is-loading');
        allowBtn.querySelector('.btn-label').textContent = 'Always Allow';
      }
    };
  }

  return { open, asciiHtml };
})();
