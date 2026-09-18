/* ==========================================================================
   FOMOJI — Sign-out experience + "CAT Shutdown Protocol" mini-game

   Deliberately dependency-free and self-contained (same shape as
   fomoji-theme.js): no bot module, no theme-engine internals required to
   function. It only *reads* existing CSS custom properties (--panel,
   --sage, --f-mono, etc.) so it inherits whatever theme/texture is active
   without importing anything from that system.

   Contract every call site relies on:
     window.FomojiSignOut.trigger(navigate?)
   Opens the small "sign out / play a game first" card. `navigate` is an
   optional function called after the real sign-out fires; defaults to
   redirecting to welcome.html. If this module fails to load, is missing,
   or throws, every call site below falls back to calling
   FomojiAPI.logout() directly — sign-out never depends on this file.

   AUTHENTICATION SAFETY: this module never touches session state itself.
   The game only ever produces one of GAME_COMPLETED / GAME_SKIPPED /
   GAME_FAILED / GAME_EXITED internally; doSignOut() is the single path
   that calls the real logout, and every button in every view (invite,
   game, error, timeout, result) routes to it. Sign Out always works,
   whether or not the game was played, won, or lost.

   No polling loops: the only timer is the countdown while the game view
   is open, cleared the instant the modal closes for any reason.
   ========================================================================== */
(function () {
  'use strict';

  if (window.FomojiSignOut) return; // already installed

  var GAME_SECONDS = 15;
  var SEQUENCE_LENGTH = 4; // NORMAL difficulty — see spec section 7

  var els = null;      // lazily-built DOM refs
  var state = {
    open: false,
    view: 'invite',   // invite | game | error | timeout | result
    navigate: null,
    timer: null,
    remaining: GAME_SECONDS,
    sequence: [],      // required click order, e.g. [3,1,4,2]
    progress: 0        // how many correct nodes powered down so far
  };

  function reduceMotion() {
    var html = document.documentElement;
    return html.classList.contains('reduce-motion') ||
      html.dataset.motion === 'reduced' || html.dataset.motion === 'none' ||
      (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function defaultNavigate() { window.location.href = 'welcome.html'; }

  // The ONLY function that ever ends a session. Nothing in the game logic
  // below calls FomojiAPI directly — it only ever calls this.
  //
  // This AWAITS the real logout before navigating. The previous
  // fire-and-forget version relied entirely on fetch keepalive to finish
  // the POST /api/logout request after the page had already started
  // navigating away — which is not guaranteed everywhere (some browsers/
  // extensions can drop a keepalive request on navigation), and could
  // make it look like "Sign Out" silently did nothing. A short timeout
  // guard keeps this from ever hanging: if the network is unreachable,
  // sign-out still proceeds and lands the user on the signed-out screen
  // client-side, which is the safe failure direction.
  function doSignOut() {
    var finished = false;
    function finish() {
      if (finished) return;
      finished = true;
      var nav = state.navigate || defaultNavigate;
      try { nav(); } catch (e) { defaultNavigate(); }
    }
    try {
      if (window.FomojiAPI && typeof FomojiAPI.logout === 'function') {
        var p = FomojiAPI.logout();
        if (p && typeof p.then === 'function') {
          p.then(finish, finish);
          setTimeout(finish, 2000); // never block sign-out on a slow/dead network
          return;
        }
      }
    } catch (e) { /* sign-out must proceed regardless */ }
    finish();
  }

  /* ---------------- DOM build (once) ---------------- */

  function build() {
    var overlay = document.createElement('div');
    overlay.className = 'fomoji-so-overlay';
    overlay.setAttribute('aria-hidden', 'true');

    overlay.innerHTML =
      '<div class="fomoji-so-panel" role="dialog" aria-modal="true" aria-labelledby="fomojiSoTitle">' +
        '<button type="button" class="fomoji-so-close" data-so-close aria-label="Cancel">\u2715</button>' +

        '<div class="fomoji-so-view" data-so-view="invite">' +
          '<div class="fomoji-so-title" id="fomojiSoTitle">Session ready to close</div>' +
          '<div class="fomoji-so-sub">Complete the shutdown sequence, or sign out now.</div>' +
          '<div class="fomoji-so-actions">' +
            '<button type="button" class="btn btn-ghost btn-inline" data-so-play>Start Shutdown</button>' +
            '<button type="button" class="btn btn-primary btn-inline" data-so-signout>Sign Out</button>' +
          '</div>' +
        '</div>' +

        '<div class="fomoji-so-view" data-so-view="game" hidden>' +
          '<div class="fomoji-so-title">CAT Shutdown Protocol</div>' +
          '<div class="fomoji-so-hud">' +
            '<span class="fomoji-so-hud-item"><span data-so-timer>' + GAME_SECONDS + '</span>s</span>' +
            '<span class="fomoji-so-hud-item" data-so-sequence>Sequence: \u2014</span>' +
          '</div>' +
          '<div class="fomoji-so-systems" aria-hidden="true">' +
            '<span class="fomoji-so-sys-label">SYSTEMS</span>' +
            '<span class="fomoji-so-dots" data-so-dots></span>' +
          '</div>' +
          '<div class="fomoji-so-arena" data-so-arena aria-label="Shutdown nodes"></div>' +
          '<div class="fomoji-so-actions">' +
            '<button type="button" class="btn btn-danger btn-inline" data-so-signout>Sign Out</button>' +
          '</div>' +
        '</div>' +

        '<div class="fomoji-so-view" data-so-view="error" hidden>' +
          '<div class="fomoji-so-title">Sequence Error</div>' +
          '<div class="fomoji-so-sub" data-so-error-sub></div>' +
          '<div class="fomoji-so-actions">' +
            '<button type="button" class="btn btn-ghost btn-inline" data-so-retry>Retry</button>' +
            '<button type="button" class="btn btn-primary btn-inline" data-so-signout>Sign Out</button>' +
          '</div>' +
        '</div>' +

        '<div class="fomoji-so-view" data-so-view="timeout" hidden>' +
          '<div class="fomoji-so-title">Shutdown Timeout</div>' +
          '<div class="fomoji-so-sub">The shutdown sequence timed out.</div>' +
          '<div class="fomoji-so-actions">' +
            '<button type="button" class="btn btn-ghost btn-inline" data-so-retry>Retry</button>' +
            '<button type="button" class="btn btn-primary btn-inline" data-so-signout>Sign Out</button>' +
          '</div>' +
        '</div>' +

        '<div class="fomoji-so-view" data-so-view="result" hidden>' +
          '<div class="fomoji-so-title" data-so-result-title>Shutdown Complete \u2713</div>' +
          '<div class="fomoji-so-sub" data-so-result-sub>Session is ready to close.</div>' +
          '<div class="fomoji-so-actions">' +
            '<button type="button" class="btn btn-primary btn-inline" data-so-signout>Sign Out</button>' +
          '</div>' +
          '<button type="button" class="fomoji-so-skip" data-so-close>Continue Session</button>' +
        '</div>' +

      '</div>';

    document.body.appendChild(overlay);

    els = {
      overlay: overlay,
      panel: overlay.querySelector('.fomoji-so-panel'),
      views: {
        invite: overlay.querySelector('[data-so-view="invite"]'),
        game: overlay.querySelector('[data-so-view="game"]'),
        error: overlay.querySelector('[data-so-view="error"]'),
        timeout: overlay.querySelector('[data-so-view="timeout"]'),
        result: overlay.querySelector('[data-so-view="result"]')
      },
      timerEl: overlay.querySelector('[data-so-timer]'),
      sequenceEl: overlay.querySelector('[data-so-sequence]'),
      dotsEl: overlay.querySelector('[data-so-dots]'),
      arena: overlay.querySelector('[data-so-arena]'),
      errorSub: overlay.querySelector('[data-so-error-sub]'),
      resultTitle: overlay.querySelector('[data-so-result-title]'),
      resultSub: overlay.querySelector('[data-so-result-sub]')
    };

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close(); // backdrop click = cancel, not sign-out
    });
    overlay.querySelectorAll('[data-so-signout]').forEach(function (btn) {
      btn.addEventListener('click', function () { close(); doSignOut(); });
    });
    overlay.querySelectorAll('[data-so-close]').forEach(function (btn) {
      btn.addEventListener('click', close);
    });
    overlay.querySelector('[data-so-play]').addEventListener('click', startGame);
    overlay.querySelectorAll('[data-so-retry]').forEach(function (btn) {
      btn.addEventListener('click', startGame);
    });

    document.addEventListener('keydown', function (e) {
      if (!state.open) return;
      if (e.key === 'Escape') { close(); }
    });
  }

  function showView(name) {
    state.view = name;
    Object.keys(els.views).forEach(function (k) {
      els.views[k].hidden = k !== name;
    });
  }

  /* ---------------- open / close ---------------- */

  function open(navigate) {
    if (!els) build();
    state.navigate = navigate || null;
    state.open = true;
    showView('invite');
    els.overlay.classList.add('is-open');
    els.overlay.setAttribute('aria-hidden', 'false');
    var playBtn = els.overlay.querySelector('[data-so-play]');
    if (playBtn) playBtn.focus();
  }

  function close() {
    stopGame();
    state.open = false;
    if (els) {
      els.overlay.classList.remove('is-open');
      els.overlay.setAttribute('aria-hidden', 'true');
    }
  }

  /* ---------------- CAT Shutdown Protocol ---------------- */

  function stopGame() {
    if (state.timer) { clearInterval(state.timer); state.timer = null; }
  }

  function shuffledSequence(n) {
    var vals = [];
    for (var i = 1; i <= n; i++) vals.push(i);
    // Fisher-Yates, re-rolled if it happens to land in ascending order
    // (ascending would make the puzzle trivially guessable).
    do {
      for (var j = vals.length - 1; j > 0; j--) {
        var k = Math.floor(Math.random() * (j + 1));
        var tmp = vals[j]; vals[j] = vals[k]; vals[k] = tmp;
      }
    } while (n > 2 && vals.every(function (v, idx) { return v === idx + 1; }));
    return vals;
  }

  function renderDots() {
    var total = state.sequence.length;
    var html = '';
    for (var i = 0; i < total; i++) {
      html += '<span class="fomoji-so-dot' + (i < state.progress ? ' is-off' : '') + '"></span>';
    }
    els.dotsEl.innerHTML = html;
  }

  function startGame() {
    stopGame();
    state.sequence = shuffledSequence(SEQUENCE_LENGTH);
    state.progress = 0;
    state.remaining = GAME_SECONDS;
    showView('game');

    els.timerEl.textContent = String(state.remaining);
    els.sequenceEl.textContent = 'Sequence: ' + state.sequence.join(' \u2192 ');
    renderDots();
    renderNodes();

    state.timer = setInterval(function () {
      state.remaining -= 1;
      els.timerEl.textContent = String(Math.max(0, state.remaining));
      if (state.remaining <= 0) {
        stopGame();
        showView('timeout');
      }
    }, 1000);
  }

  function renderNodes() {
    els.arena.innerHTML = '';
    // Fixed grid positions (not randomly floating) — this is a sequence
    // puzzle, not a reflex/catch game, so nodes stay put and are fully
    // keyboard-tabbable in DOM order.
    var order = state.sequence.slice().sort(function (a, b) { return a - b; });
    // Display order is scrambled independently of the required click
    // order so the puzzle isn't just "click left to right".
    var display = order.slice();
    for (var s = display.length - 1; s > 0; s--) {
      var r = Math.floor(Math.random() * (s + 1));
      var t = display[s]; display[s] = display[r]; display[r] = t;
    }
    display.forEach(function (value) {
      var node = document.createElement('button');
      node.type = 'button';
      node.className = 'fomoji-so-node';
      node.textContent = String(value);
      node.setAttribute('aria-label', 'Node ' + value);
      node.dataset.soValue = String(value);
      if (reduceMotion()) node.classList.add('no-motion');
      node.addEventListener('click', function () { selectNode(node, value); });
      els.arena.appendChild(node);
    });
  }

  function selectNode(node, value) {
    if (!state.open || state.view !== 'game' || node.disabled) return;
    var expected = state.sequence[state.progress];
    if (value !== expected) {
      stopGame();
      node.classList.add('is-error');
      els.errorSub.textContent = 'Expected node ' + expected + ', got node ' + value + '.';
      showView('error');
      return;
    }
    node.disabled = true;
    node.classList.add('is-off');
    state.progress += 1;
    renderDots();
    if (state.progress >= state.sequence.length) {
      endGame();
    }
  }

  function endGame() {
    stopGame();
    els.resultTitle.textContent = 'Shutdown Complete \u2713';
    els.resultSub.textContent = 'Session is ready to close.';
    showView('result');
    var focusTarget = els.overlay.querySelector('[data-so-signout]');
    if (focusTarget) focusTarget.focus();
  }

  /* ---------------- public API ---------------- */

  function trigger(navigate) {
    var nav = typeof navigate === 'function' ? navigate : null;
    state.navigate = nav;
    try {
      open(nav);
    } catch (e) {
      // The one rule that can never break: Sign Out still has to work.
      doSignOut();
    }
  }

  window.FomojiSignOut = { trigger: trigger };
})();
