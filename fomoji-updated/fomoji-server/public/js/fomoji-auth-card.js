/* ==========================================================================
   FOMOJI — Authentication Card (client)

   Talks to src/routes/authCard.js. Read that file's header comment before
   changing any copy in here — the honesty boundary around "verified" vs
   "screenshot" is load-bearing and both files must say the same thing.

   Requires (loaded by whatever page opens the modal, in this order):
     <script src="vendor/simplewebauthn-browser.min.js"></script>  (for passkey unlock)
     <script src="js/fomoji-auth.js"></script>                     (FomojiAuthError)
     <script src="js/fomoji-auth-card.js"></script>                (this file)
   Three.js itself is lazy-loaded from a CDN only when the modal actually
   opens, so pages that never open the card pay nothing for it.
   ========================================================================== */

class FomojiCardError extends Error {}

const FomojiAuthCard = (() => {
  const THREE_CDN = 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js';
  let threePromise = null;

  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    if (threePromise) return threePromise;
    threePromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = THREE_CDN;
      s.onload = () => resolve(window.THREE);
      s.onerror = () => reject(new FomojiCardError('Could not load the 3D renderer. Check your connection.'));
      document.head.appendChild(s);
    });
    return threePromise;
  }

  function humanizeError(code) {
    switch (code) {
      case 'invalid_credentials': return 'That didn\u2019t match. Try again.';
      case 'no_passkey': return 'This identity has no passkey to unlock with — use your password or PIN instead.';
      case 'unlock_required': return 'Unlock required.';
      case 'invalid_pin': return 'PIN must be 4\u201332 characters.';
      case 'invalid_recovery': return 'That recovery code doesn\u2019t match this account.';
      case 'not_authenticated': return 'You need to be signed in to do that.';
      default: return 'Something went wrong. Try again.';
    }
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new FomojiCardError(data.message || humanizeError(data.error));
    return data;
  }

  // ---- seeded deterministic PRNG (mulberry32) so the same server-issued
  // pattern_seed always draws the identical pattern client-side, without
  // the seed itself needing to leave the server as anything but hex. ----
  function mulberry32(seedHex) {
    let a = parseInt(seedHex.slice(0, 8), 16) >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Renders the per-user pattern into `container` (a DOM element) using
  // Three.js, seeded entirely from patternSeed. Returns a `dispose()` fn.
  async function renderPattern(container, patternSeed) {
    const THREE = await loadThree();
    const rand = mulberry32(patternSeed);
    // Pull several independent streams out of the one seed so shape count,
    // palette, and layout don't all move together.
    const hueBase = rand() * 360;
    const shapeCount = 14 + Math.floor(rand() * 10);
    const shapeKind = Math.floor(rand() * 3); // 0=icosahedron, 1=octahedron, 2=torus

    const width = container.clientWidth || 320;
    const height = container.clientHeight || 320;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 0, 9);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(3, 4, 5);
    scene.add(key);

    const group = new THREE.Group();
    for (let i = 0; i < shapeCount; i++) {
      const hue = (hueBase + rand() * 70 - 35 + 360) % 360;
      const color = new THREE.Color().setHSL(hue / 360, 0.42, 0.5 + rand() * 0.18);
      let geo;
      if (shapeKind === 0) geo = new THREE.IcosahedronGeometry(0.24 + rand() * 0.22, 0);
      else if (shapeKind === 1) geo = new THREE.OctahedronGeometry(0.24 + rand() * 0.22, 0);
      else geo = new THREE.TorusGeometry(0.18 + rand() * 0.14, 0.06 + rand() * 0.05, 8, 16);
      const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.25 });
      const mesh = new THREE.Mesh(geo, mat);

      const radius = 1.2 + rand() * 2.6;
      const theta = rand() * Math.PI * 2;
      const phi = Math.acos(rand() * 2 - 1);
      mesh.position.set(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.sin(phi) * Math.sin(theta),
        radius * Math.cos(phi) * 0.6
      );
      mesh.rotation.set(rand() * Math.PI, rand() * Math.PI, rand() * Math.PI);
      mesh.userData.spin = 0.08 + rand() * 0.18;
      mesh.userData.axis = new THREE.Vector3(rand() - 0.5, rand() - 0.5, rand() - 0.5).normalize();
      group.add(mesh);
    }
    scene.add(group);

    let raf = null;
    let disposed = false;
    function tick() {
      if (disposed) return;
      group.rotation.y += 0.0022;
      group.children.forEach((m) => m.rotateOnAxis(m.userData.axis, m.userData.spin * 0.01));
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    }
    tick();

    return function dispose() {
      disposed = true;
      if (raf) cancelAnimationFrame(raf);
      group.children.forEach((m) => { m.geometry.dispose(); m.material.dispose(); });
      renderer.dispose();
    };
  }

  return {
    async unlockWithPassword(password) {
      return postJSON('/api/auth-card/unlock/password', { password });
    },
    async unlockWithPin(pin) {
      return postJSON('/api/auth-card/unlock/pin', { pin });
    },
    async unlockWithPasskey() {
      const { options } = await postJSON('/api/auth-card/unlock/webauthn/start', undefined);
      let asseResp;
      try {
        asseResp = await SimpleWebAuthnBrowser.startAuthentication({ optionsJSON: options });
      } catch (err) {
        console.error('[fomoji:auth-card] passkey unlock cancelled/failed —', err && err.name, err && err.message);
        throw new FomojiCardError('Cancelled, or your device didn\u2019t respond in time.');
      }
      return postJSON('/api/auth-card/unlock/webauthn/finish', asseResp);
    },
    async unlockWithRecovery(recoveryCode) {
      return postJSON('/api/auth-card/unlock/recovery', { recoveryCode });
    },
    async setPin(pin) {
      return postJSON('/api/auth-card/pin', { pin });
    },
    // Which unlock methods this identity actually has, so the modal can
    // show the right primary action instead of guessing. Safe to call
    // before any unlock — see the route's own comment for why.
    async unlockStatus() {
      const res = await fetch('/api/auth-card/unlock-status', { credentials: 'same-origin' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new FomojiCardError(humanizeError(data.error));
      return data;
    },
    async getCard() {
      const res = await fetch('/api/auth-card/', { credentials: 'same-origin' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new FomojiCardError(humanizeError(data.error));
      return data;
    },
    async verify(card) {
      return postJSON('/api/auth-card/verify', {
        fomojiId: card.fomojiId, patternSeed: card.patternSeed, signature: card.signature,
      });
    },
    renderPattern,

    // Downloads the card as a single JSON file carrying the actual
    // signed data (fomojiId + patternSeed + signature + issuedAt) — this
    // is what makes a download verifiable where a screenshot isn't: the
    // screenshot only has pixels, this file has the data /verify checks.
    downloadCard(card) {
      const blob = new Blob([JSON.stringify(card, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fomoji-authentication-card-${card.fomojiId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },

    // ---- the full modal: unlock -> render -> download ----
    async open() {
      let modal = document.getElementById('fomojiCardModal');
      if (!modal) {
        modal = document.createElement('div');
        modal.id = 'fomojiCardModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
          <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="cardModalTitle" style="max-width:420px;">
            <div class="modal-title" id="cardModalTitle">Fomoji Authentication Card</div>
            <div id="cardModalBody"></div>
          </div>`;
        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => { if (e.target === modal) { modal.classList.remove('is-open'); if (modal._disposePattern) { modal._disposePattern(); modal._disposePattern = null; } } });
      }
      const body = document.getElementById('cardModalBody');

      function close() {
        modal.classList.remove('is-open');
        if (modal._disposePattern) { modal._disposePattern(); modal._disposePattern = null; }
      }

      async function renderUnlockStep() {
        body.innerHTML = `<p class="modal-body">Checking how this identity unlocks\u2026</p>`;

        let status;
        try {
          status = await FomojiAuthCard.unlockStatus();
        } catch (err) {
          body.innerHTML = `<div class="alert alert-error is-visible">${err instanceof FomojiCardError ? err.message : 'Could not load your card.'}</div>`;
          return;
        }

        // Nothing to unlock against (no passkey, no password, no PIN) —
        // the server already treats this identity as unlocked in that
        // case (see routes/authCard.js), so just go straight to the card
        // instead of showing a step-up screen with nothing to step up
        // against. Still nudge toward setting up a real unlock method,
        // since anyone with the session cookie can otherwise open it.
        if (!status.unlockRequired) {
          await renderCardStep({ nudgeSetup: true });
          return;
        }

        const primaryIsPasskey = status.hasPasskey;
        const hasSecret = status.hasPassword || status.hasPin;

        body.innerHTML = `
          <p class="modal-body">Your card holds your full account info and proves your recovery code exists — so it's locked behind a fresh device check first, same as unlocking a passkey.</p>
          ${primaryIsPasskey ? `
            <button class="btn btn-primary" id="cardUnlockPasskey" style="width:100%; justify-content:center; margin-bottom:8px;">Unlock with device authentication</button>
            <div style="text-align:center; font-size:11px; color:var(--ink-faint); margin:8px 0;">Face ID · Touch ID · Windows Hello · security key</div>
          ` : `
            <div class="alert" style="font-size:12.5px; color:var(--ink-dim); background:var(--panel-2); border:1px solid var(--line); border-radius:var(--radius-s); padding:10px 12px; margin-bottom:10px;">
              This identity doesn\u2019t have a passkey yet${hasSecret ? ' — use your password or PIN below, or add one now.' : '.'}
            </div>
            <button class="btn btn-ghost" id="cardCreatePasskey" style="width:100%; justify-content:center; margin-bottom:10px;">Create a passkey</button>
          `}
          ${hasSecret ? `
            <div class="field" style="margin-top:${primaryIsPasskey ? '6px' : '0'};">
              <input type="password" id="cardUnlockSecret" placeholder="Password or PIN">
            </div>
            <button class="btn ${primaryIsPasskey ? 'btn-ghost' : 'btn-primary'}" id="cardUnlockSecretBtn" style="width:100%; justify-content:center; margin-top:8px;">Unlock</button>
          ` : ''}
          <button type="button" id="cardForgotBtn" style="display:block; width:100%; margin-top:10px; background:none; border:none; cursor:pointer; font-size:12px; color:var(--ink-faint); text-align:center; padding:4px;">Forgot passkey, password, or PIN?</button>
          <div id="cardRecoveryRow" style="display:none; margin-top:10px;">
            <div class="field">
              <input type="text" id="cardRecoveryCode" placeholder="Recovery code" autocapitalize="characters">
            </div>
            <button class="btn btn-ghost" id="cardRecoveryBtn" style="width:100%; justify-content:center; margin-top:8px;">Unlock with recovery code</button>
          </div>
          <div class="alert alert-error" id="cardUnlockAlert" role="alert"></div>
          <div class="modal-actions" style="margin-top:14px;">
            <button type="button" class="btn btn-ghost" id="cardCloseBtn">Close</button>
          </div>`;

        document.getElementById('cardCloseBtn').addEventListener('click', close);

        const alertEl = document.getElementById('cardUnlockAlert');
        function showErr(msg) { alertEl.textContent = msg; alertEl.classList.add('is-visible'); }

        const passkeyBtn = document.getElementById('cardUnlockPasskey');
        if (passkeyBtn) {
          passkeyBtn.addEventListener('click', async (e) => {
            e.target.disabled = true;
            try {
              await FomojiAuthCard.unlockWithPasskey();
              await renderCardStep();
            } catch (err) {
              showErr(err instanceof FomojiCardError ? err.message : 'Something went wrong.');
              e.target.disabled = false;
            }
          });
        }

        const createPasskeyBtn = document.getElementById('cardCreatePasskey');
        if (createPasskeyBtn) {
          createPasskeyBtn.addEventListener('click', () => {
            if (!window.FomojiPasskeyManager) { showErr('Passkey creation isn\u2019t available on this page.'); return; }
            FomojiPasskeyManager.openCreateModal({
              onCreated: () => renderUnlockStep(), // re-check status: passkey now exists
            });
          });
        }

        const secretBtn = document.getElementById('cardUnlockSecretBtn');
        if (secretBtn) {
          secretBtn.addEventListener('click', async () => {
            const val = document.getElementById('cardUnlockSecret').value;
            if (!val) return;
            try {
              // Try PIN first if one's set on this identity is unknown client-side,
              // so just attempt password; on failure attempt PIN. Cheap and no
              // extra round trip in the common case (password is far more likely).
              try {
                await FomojiAuthCard.unlockWithPassword(val);
              } catch {
                await FomojiAuthCard.unlockWithPin(val);
              }
              await renderCardStep();
            } catch (err) {
              showErr(err instanceof FomojiCardError ? err.message : 'That didn\u2019t match either your password or your PIN.');
            }
          });
        }

        document.getElementById('cardForgotBtn').addEventListener('click', () => {
          const row = document.getElementById('cardRecoveryRow');
          row.style.display = row.style.display === 'none' ? 'block' : 'none';
          if (row.style.display === 'block') document.getElementById('cardRecoveryCode').focus();
        });
        document.getElementById('cardRecoveryBtn').addEventListener('click', async () => {
          const code = document.getElementById('cardRecoveryCode').value;
          if (!code) return;
          try {
            await FomojiAuthCard.unlockWithRecovery(code);
            await renderCardStep();
          } catch (err) {
            showErr(err instanceof FomojiCardError ? err.message : 'That recovery code didn\u2019t match.');
          }
        });
      }

      async function renderCardStep(opts) {
        opts = opts || {};
        body.innerHTML = `
          ${opts.nudgeSetup ? `
            <div class="alert" style="font-size:12px; color:var(--gold); background:rgba(201,160,74,0.08); border:1px solid rgba(201,160,74,0.35); border-radius:var(--radius-s); padding:10px 12px; margin-bottom:12px;">
              This identity has no passkey, password, or PIN set, so anyone with an open session here could view this card. Add a passkey to protect it.
              <button type="button" id="cardNudgeCreatePasskey" class="btn btn-ghost btn-inline" style="margin-top:8px; width:100%; justify-content:center;">Create a passkey</button>
            </div>
          ` : ''}
          <div id="cardPatternHost" style="width:100%; aspect-ratio:1/1; border-radius:var(--radius-m); overflow:hidden; background:var(--panel-2); border:1px solid var(--line); margin-bottom:14px;"></div>
          <div style="font-family:var(--f-mono); font-size:12px; line-height:1.9;" id="cardFields"></div>
          <div id="cardVerifyBadge" style="margin:10px 0; font-size:11.5px;"></div>
          <button class="btn btn-primary" id="cardDownloadBtn" style="width:100%; justify-content:center; margin-top:6px;">Download card</button>
          <div class="doc-note is-honest" style="margin-top:12px;">
            A <strong>download</strong> carries this card's signed data, so it verifies. A <strong>screenshot</strong> only captures pixels — it carries no signature, so it can't be verified through Fomoji even though it looks identical. That's what actually distinguishes them: not that a screenshot is detected or blocked (no website can do that), but that only the real data verifies.
          </div>
          <div class="modal-actions" style="margin-top:14px;">
            <button type="button" class="btn btn-ghost" id="cardCloseBtn2">Close</button>
          </div>`;
        document.getElementById('cardCloseBtn2').addEventListener('click', close);

        const nudgeBtn = document.getElementById('cardNudgeCreatePasskey');
        if (nudgeBtn) {
          nudgeBtn.addEventListener('click', () => {
            if (!window.FomojiPasskeyManager) return;
            FomojiPasskeyManager.openCreateModal({ onCreated: () => renderCardStep() });
          });
        }

        try {
          const card = await FomojiAuthCard.getCard();
          const host = document.getElementById('cardPatternHost');
          modal._disposePattern = await renderPattern(host, card.patternSeed);

          document.getElementById('cardFields').innerHTML = `
            <div>${card.fomojiId}</div>
            <div>${card.name || ''}</div>
            <div>@${card.username}</div>
            <div>${card.email || ''}</div>
            <div style="color:var(--ink-faint);">Recovery code: ${card.hasRecoveryCode ? 'set' : 'not set'}</div>
            <div style="color:var(--ink-faint);">Issued ${new Date(card.issuedAt).toLocaleString()}</div>`;

          const { verified } = await FomojiAuthCard.verify(card);
          const badge = document.getElementById('cardVerifyBadge');
          badge.innerHTML = verified
            ? `<span class="pill pill-on">Verified by Fomoji</span>`
            : `<span class="pill pill-off">Not verified</span>`;

          document.getElementById('cardDownloadBtn').addEventListener('click', () => FomojiAuthCard.downloadCard(card));
        } catch (err) {
          body.innerHTML = `<div class="alert alert-error is-visible">${err instanceof FomojiCardError ? err.message : 'Could not load your card.'}</div>`;
        }
      }

      renderUnlockStep();
      modal.classList.add('is-open');
    },
  };
})();
