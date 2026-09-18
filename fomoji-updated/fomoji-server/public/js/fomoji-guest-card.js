/* ==========================================================================
   FOMOJI — Guest Card

   window.FomojiGuestCard.render(container, account, opts?)

   `account` must be a guest account shape from FomojiAPI (isGuest: true).
   `opts.connected` (bool) — whether CAT is connected for this guest
   session; pass FomojiAPI.getConnections(account).cat if the caller
   already knows it, otherwise this reads it itself when FomojiAPI is on
   the page. `opts.createAccountHref` / `opts.manageHref` override the
   default links (signup.html / settings.html).

   Guest is a real, first-class Fomoji identity/session type (spec
   section 3) — this card is deliberately styled like the other identity
   cards (Group/Student/Temporary), never like an error or a nag.
   ========================================================================== */
(function () {
  'use strict';

  function fmtTime(ts) {
    try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
    catch (e) { return '—'; }
  }

  function render(container, account, opts) {
    if (!container || !account || !account.isGuest) return null;
    opts = opts || {};

    var connected = opts.connected;
    if (connected === undefined) {
      try { connected = !!(window.FomojiAPI && FomojiAPI.getConnections(account).cat); }
      catch (e) { connected = false; }
    }

    var createHref = opts.createAccountHref || 'signup.html';
    var manageHref = opts.manageHref || 'settings.html';

    var card = document.createElement('div');
    card.className = 'fomoji-guest-card';
    card.setAttribute('role', 'group');
    card.setAttribute('aria-label', 'Fomoji guest session');

    card.innerHTML =
      '<div class="fomoji-guest-card-top">' +
        '<span class="fomoji-guest-card-eyebrow">Fomoji Guest</span>' +
        '<span class="fomoji-guest-card-badge">Temporary</span>' +
      '</div>' +
      '<div class="fomoji-guest-card-id">' + escapeHtml(account.username || 'guest') + '</div>' +
      '<div class="fomoji-guest-card-rows">' +
        '<div class="fomoji-guest-card-row"><span>Session</span><span>Temporary — this browser tab only</span></div>' +
        '<div class="fomoji-guest-card-row"><span>CAT</span><span>' + (connected ? 'Connected' : 'Not connected') + '</span></div>' +
        '<div class="fomoji-guest-card-row"><span>Session expires</span><span>' + (account.expiresAt ? fmtTime(account.expiresAt) : '—') + '</span></div>' +
      '</div>' +
      '<div class="fomoji-guest-card-actions">' +
        '<a class="btn btn-primary btn-inline" href="' + createHref + '">Create Account</a>' +
        '<a class="btn btn-ghost btn-inline" href="' + manageHref + '">Manage Guest Session</a>' +
      '</div>';

    container.innerHTML = '';
    container.appendChild(card);
    return card;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  window.FomojiGuestCard = { render: render };
})();
