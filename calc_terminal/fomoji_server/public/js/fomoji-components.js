/* ==========================================================================
   FOMOJI — COMPONENT / INTERACTION ENGINE  (UI Engine 2.0, Phase 1)

   One wiring pass for every interactive component instead of one-off
   listeners per button/tab. Concretely, this file:

     1. Registers component "kinds" (button, tab, card, input) by selector,
        matching the classes fomoji.css already uses (.btn, .tab, .card,
        .field input) — no HTML changes required for existing pages.
     2. Drives a single state machine (hover / focus / press / active /
        loading / success / error / disabled) from pointer, touch, AND
        keyboard input, and reflects it as a `data-fx-state` attribute plus
        a `fomoji-fx-state` CustomEvent — so mouse-only :hover in the old
        CSS keeps working, and anything new (Glow Engine, Liquid Glass
        bounce/stretch) can hook the same attribute for every component
        kind at once instead of re-deriving state itself.
     3. Exposes window.FomojiComponents so later phases register new kinds
        (e.g. a Liquid Glass surface) or new state handlers without needing
        to touch this file or duplicate the event wiring.

   This is purely an interaction layer. It never touches auth, routing, or
   any application logic — it only ever reads/writes visual state attributes
   on the DOM. Load after fomoji-theme.js (state should reflect the current
   theme's motion settings) and before fomoji-fx.js.
   ========================================================================== */
(function () {
  'use strict';

  var KINDS = {
    button: { selector: '.btn, [data-fx="button"]' },
    tab:    { selector: '.tab, [data-fx="tab"]' },
    card:   { selector: '.card, .dash-card, [data-fx="card"]' },
    input:  { selector: '.field input, [data-fx="input"]' }
  };

  var wired = new WeakSet();

  function motionAllowed() {
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var mode = document.documentElement.dataset.motion;
    return !reduced && mode !== 'reduced' && mode !== 'none'
      && !document.documentElement.classList.contains('reduce-motion');
  }

  function setState(el, state) {
    if (el.getAttribute('data-fx-state') === state) return;
    if (state) el.setAttribute('data-fx-state', state);
    else el.removeAttribute('data-fx-state');
    el.dispatchEvent(new CustomEvent('fomoji-fx-state', {
      bubbles: true,
      detail: { state: state, motion: motionAllowed() }
    }));
  }

  function isDisabled(el) {
    return el.disabled === true || el.getAttribute('aria-disabled') === 'true'
      || el.classList.contains('is-disabled');
  }

  function syncDisabled(el) {
    if (isDisabled(el)) el.setAttribute('data-fx-disabled', 'true');
    else el.removeAttribute('data-fx-disabled');
  }

  function wireElement(el, kind) {
    if (wired.has(el)) return;
    wired.add(el);
    syncDisabled(el);

    var pressed = false, hovering = false, focused = false;

    function refresh() {
      if (isDisabled(el)) { setState(el, 'disabled'); return; }
      if (el.classList.contains('is-loading')) { setState(el, 'loading'); return; }
      if (el.classList.contains('is-success')) { setState(el, 'success'); return; }
      if (el.classList.contains('is-error')) { setState(el, 'error'); return; }
      if (pressed) { setState(el, 'press'); return; }
      if (focused) { setState(el, 'focus'); return; }
      if (hovering) { setState(el, 'hover'); return; }
      setState(el, null);
    }

    el.addEventListener('pointerenter', function () { hovering = true; refresh(); });
    el.addEventListener('pointerleave', function () { hovering = false; pressed = false; refresh(); });
    el.addEventListener('pointerdown', function () { pressed = true; refresh(); });
    el.addEventListener('pointerup', function () { pressed = false; refresh(); });
    el.addEventListener('pointercancel', function () { pressed = false; refresh(); });
    el.addEventListener('focus', function () { focused = true; refresh(); });
    el.addEventListener('blur', function () { focused = false; pressed = false; refresh(); });
    // class-driven states (loading/success/error/disabled) can change without
    // a pointer/focus event firing — watch for that so data-fx-state stays honest
    new MutationObserver(refresh).observe(el, { attributes: true, attributeFilter: ['class', 'disabled', 'aria-disabled'] });

    // ---- universal press/release bounce (buttons AND tabs, every texture) ----
    // This used to live only in fomoji-liquid-glass.js, gated to .btn and to
    // data-texture="liquid" — so .tab (the tab bar) never got a bounce at
    // all, in any texture, and every non-Liquid-Glass button had no press
    // feedback beyond an almost-imperceptible native :active scale. Wiring
    // it here instead, keyed off the same fomoji-fx-state event every
    // component kind already emits, fixes both at once and for free covers
    // any future component kind that starts emitting that event.
    if (kind === 'button' || kind === 'tab') {
      el.addEventListener('fomoji-fx-state', function (e) {
        if (!e.detail) return;
        if (e.detail.state === 'press') {
          el.classList.remove('fx-bounce');
          el.classList.add('fx-press');
        } else if (el.classList.contains('fx-press')) {
          el.classList.remove('fx-press');
          if (e.detail.motion) {
            el.classList.remove('fx-bounce');
            // force reflow so re-adding the class restarts the animation
            // even if it's re-triggered before the previous run finished
            void el.offsetWidth;
            el.classList.add('fx-bounce');
          }
        }
      });
      el.addEventListener('animationend', function (e) {
        if (e.animationName === 'fx-bounce-kf') el.classList.remove('fx-bounce');
      });
    }

    refresh();
  }

  function wireAll(root) {
    Object.keys(KINDS).forEach(function (kind) {
      var els = (root || document).querySelectorAll(KINDS[kind].selector);
      els.forEach(function (el) { wireElement(el, kind); });
    });
  }

  function boot() {
    wireAll(document);
    // pages/components can be injected later (e.g. a modal) — watch for that
    var mo = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes && m.addedNodes.forEach(function (node) {
          if (node.nodeType === 1) wireAll(node);
        });
      });
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  window.FomojiComponents = {
    kinds: KINDS,
    /** Register a new component kind (selector) for future phases to build on. */
    registerKind: function (name, selector) {
      KINDS[name] = { selector: selector };
      wireAll(document);
    },
    /** Manually (re)wire a subtree — useful after injecting new markup. */
    wire: wireAll,
    motionAllowed: motionAllowed
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
