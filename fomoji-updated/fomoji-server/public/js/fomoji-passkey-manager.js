/* ==========================================================================
   FOMOJI — Passkey creation (custom-named)

   Requires (loaded by whatever page uses this, in this order):
     <script src="vendor/simplewebauthn-browser.min.js"></script>
     <script src="js/fomoji-webauthn.js"></script>   (FomojiWebAuthn, FomojiWebAuthnError)
     <script src="js/fomoji-passkey-manager.js"></script>  (this file)

   This does NOT replace fomoji-webauthn.js's addPasskey() — it wraps it.
   addPasskey() runs the real WebAuthn ceremony and inserts the credential
   with an auto-guessed nickname (from the User-Agent) the instant it's
   created, because the credential must exist in the DB before it can be
   renamed. This module's only job is the second, optional step: if the
   caller supplied a custom name, rename the credential that was just
   created to that name via the existing PATCH /api/credentials/:id route
   — no new server surface needed for that part.

   Two ways to use it:
     FomojiPasskeyManager.createNamedPasskey(name) -> Promise
       Headless — just runs the ceremony + optional rename. Use this if
       you already have your own UI (e.g. embedded in another modal, like
       the Authentication Card's unlock screen).

     FomojiPasskeyManager.openCreateModal(opts?)
       Self-contained modal: name field + "Create passkey" button. Calls
       opts.onCreated(credential) on success, opts.onCancel() on cancel.
   ========================================================================== */
(function () {
  'use strict';

  async function createNamedPasskey(customName) {
    const result = await FomojiWebAuthn.addPasskey(); // real ceremony; throws FomojiWebAuthnError on cancel/failure
    const trimmed = (customName || '').trim();
    if (trimmed) {
      try {
        const creds = await FomojiWebAuthn.listCredentials(); // ordered oldest -> newest
        const newest = creds[creds.length - 1];
        if (newest) await FomojiWebAuthn.renameCredential(newest.id, trimmed.slice(0, 60));
      } catch (e) {
        // Non-fatal: the passkey itself was created successfully and
        // works for sign-in/unlock either way — a failed rename just
        // means it keeps its auto-guessed name. Don't fail the whole
        // operation over a cosmetic label.
        console.warn('[fomoji:passkey-manager] passkey created but custom name failed to save —', e);
      }
    }
    return result;
  }

  function openCreateModal(opts) {
    opts = opts || {};
    let modal = document.getElementById('fomojiPasskeyCreateModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'fomojiPasskeyCreateModal';
      modal.className = 'modal-overlay';
      modal.innerHTML = `
        <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="pkCreateTitle" style="max-width:380px;">
          <div class="modal-title" id="pkCreateTitle">Add a passkey</div>
          <p class="modal-body">Your device will ask for Face ID, Touch ID, Windows Hello, or a security key. Give it a name so you can tell it apart later — e.g. "Work laptop" or "YubiKey".</p>
          <div class="field">
            <input type="text" id="pkCreateName" placeholder="Passkey name (optional)" maxlength="60">
          </div>
          <div class="alert alert-error" id="pkCreateAlert" role="alert"></div>
          <div class="modal-actions" style="margin-top:14px; display:flex; gap:8px;">
            <button type="button" class="btn btn-ghost" id="pkCreateCancel">Cancel</button>
            <button type="button" class="btn btn-primary" id="pkCreateGo" style="flex:1;">Create passkey</button>
          </div>
        </div>`;
      document.body.appendChild(modal);
      modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
    }

    function close() {
      modal.classList.remove('is-open');
      if (typeof opts.onCancel === 'function') opts.onCancel();
    }

    const alertEl = modal.querySelector('#pkCreateAlert');
    const nameInput = modal.querySelector('#pkCreateName');
    const goBtn = modal.querySelector('#pkCreateGo');
    const cancelBtn = modal.querySelector('#pkCreateCancel');

    alertEl.classList.remove('is-visible');
    alertEl.textContent = '';
    nameInput.value = '';
    goBtn.disabled = false;

    // Fresh listeners each open (previous ones removed via cloning) so
    // repeated opens on the same page don't stack duplicate handlers.
    const freshGoBtn = goBtn.cloneNode(true);
    goBtn.parentNode.replaceChild(freshGoBtn, goBtn);
    const freshCancelBtn = cancelBtn.cloneNode(true);
    cancelBtn.parentNode.replaceChild(freshCancelBtn, cancelBtn);

    freshCancelBtn.addEventListener('click', close);
    freshGoBtn.addEventListener('click', async () => {
      freshGoBtn.disabled = true;
      alertEl.classList.remove('is-visible');
      try {
        const result = await createNamedPasskey(nameInput.value);
        modal.classList.remove('is-open');
        if (typeof opts.onCreated === 'function') opts.onCreated(result);
      } catch (err) {
        alertEl.textContent = (err && err.message) || 'Could not create that passkey. Try again.';
        alertEl.classList.add('is-visible');
        freshGoBtn.disabled = false;
      }
    });

    modal.classList.add('is-open');
    nameInput.focus();
  }

  window.FomojiPasskeyManager = { createNamedPasskey, openCreateModal };
})();
