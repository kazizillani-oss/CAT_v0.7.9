/* ==========================================================================
   FOMOJI — LIQUID GLASS DRIVER  (UI Engine 2.0, Phase 2)

   Companion to css/fomoji-liquid-glass.css. Does three things, all scoped
   to html[data-texture="liquid"] so it's a no-op on every other texture:

     1. Moves the specular highlight (--lg-x/--lg-y) to follow the pointer
        on any liquid-glass surface.
     2. Listens for the `fomoji-fx-state` events js/fomoji-components.js
        already dispatches (Phase 1) to drive press-compress + release-bounce
        on .btn, instead of wiring its own pointerdown/up handlers.
     3. Adds pointer-direction stretch (--lg-stretch-x/-y) while pressed.
     4. Positions a floating `.tab-indicator` behind the active tab in the
        liquid-glass tab bar, sized/placed from the real DOM (not hardcoded),
        and re-measures on resize/appearance change.

   Never touches auth, routing, or app logic — visual state only.
   Load after js/fomoji-components.js.
   ========================================================================== */
(function () {
  'use strict';

  function isLiquid() {
    return document.documentElement.dataset.texture === 'liquid';
  }

  function motionAllowed() {
    return window.FomojiComponents ? window.FomojiComponents.motionAllowed() : true;
  }

  /* ---- 1 & 3: pointer-tracked highlight + press stretch ---- */
  var STRETCH_SELECTOR = '.btn, .card, .dash-card, .panel, .tabbar';

  function bindSurface(el) {
    if (el.dataset.lgBound) return;
    el.dataset.lgBound = '1';

    var pressing = false, startX = 0, startY = 0;

    el.addEventListener('pointermove', function (e) {
      if (!isLiquid()) return;
      var r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      var x = ((e.clientX - r.left) / r.width) * 100;
      var y = ((e.clientY - r.top) / r.height) * 100;
      el.style.setProperty('--lg-x', x.toFixed(1) + '%');
      el.style.setProperty('--lg-y', y.toFixed(1) + '%');

      if (pressing && motionAllowed()) {
        var strength = getComputedStyle(document.documentElement).getPropertyValue('--fx-stretch-strength').trim();
        var s = parseFloat(strength) || 0;
        if (s > 0) {
          var dx = ((e.clientX - startX) / r.width) * 10 * s;   // small, physical, not gimmicky
          var dy = ((e.clientY - startY) / r.height) * 10 * s;
          el.style.setProperty('--lg-stretch-x', dx.toFixed(2) + 'px');
          el.style.setProperty('--lg-stretch-y', dy.toFixed(2) + 'px');
        }
      }
    });

    el.addEventListener('pointerdown', function (e) {
      pressing = true;
      startX = e.clientX; startY = e.clientY;
    });

    function release() {
      pressing = false;
      el.style.setProperty('--lg-stretch-x', '0px');
      el.style.setProperty('--lg-stretch-y', '0px');
    }
    el.addEventListener('pointerup', release);
    el.addEventListener('pointercancel', release);
    el.addEventListener('pointerleave', function () {
      release();
      el.style.setProperty('--lg-x', '50%');
      el.style.setProperty('--lg-y', '30%');
    });
  }

  function bindAllSurfaces(root) {
    (root || document).querySelectorAll(STRETCH_SELECTOR).forEach(bindSurface);
  }

  /* ---- 2: press-compress + release-bounce, driven by fomoji-components.js ---- */
  document.addEventListener('fomoji-fx-state', function (e) {
    if (!isLiquid()) return;
    var el = e.target;
    if (!el.classList || !el.classList.contains('btn')) return;

    if (e.detail.state === 'press') {
      el.classList.add('lg-press');
      return;
    }
    // leaving press -> release. Only bounce if we were actually pressed.
    if (el.classList.contains('lg-press')) {
      el.classList.remove('lg-press');
      if (motionAllowed()) {
        el.classList.remove('lg-bounce'); // restart if mid-bounce
        void el.offsetWidth; // force reflow so the animation replays
        el.classList.add('lg-bounce');
        el.addEventListener('animationend', function handler() {
          el.classList.remove('lg-bounce');
          el.removeEventListener('animationend', handler);
        });
      }
    }
  });

  /* ---- 4: floating tab-bar indicator ---- */
  function positionIndicator() {
    var tabbar = document.querySelector('.tabbar');
    if (!tabbar) return;

    if (!isLiquid()) {
      var existing = tabbar.querySelector('.tab-indicator');
      if (existing) existing.remove();
      return;
    }

    var active = tabbar.querySelector('.tab.is-active');
    if (!active) return;

    var indicator = tabbar.querySelector('.tab-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'tab-indicator';
      indicator.setAttribute('aria-hidden', 'true');
      tabbar.insertBefore(indicator, tabbar.firstChild);
    }

    var barRect = tabbar.getBoundingClientRect();
    var tabRect = active.getBoundingClientRect();
    // getBoundingClientRect() returns the BORDER edge, but this indicator is
    // position:absolute inside .tabbar, so its left/top are resolved against
    // the PADDING edge of that containing block, not the border edge. With
    // .tabbar's 1px border, subtracting barRect directly left every
    // indicator on every page offset by the border width — small on its
    // own, but combined with any rounding it's what made the pill look like
    // it never quite lined up with its tab. clientLeft/clientTop report the
    // border width (0 if borders are ever removed), so subtracting them
    // corrects the offset properly instead of guessing a fixed 1px.
    var borderLeft = tabbar.clientLeft || 0;
    var borderTop = tabbar.clientTop || 0;
    indicator.style.left = (tabRect.left - barRect.left - borderLeft) + 'px';
    indicator.style.width = tabRect.width + 'px';
    // top/height were the one part still hardcoded in CSS (6px/52px, sized
    // for the default floating tab). Measuring them here too means the
    // indicator actually matches compact's 44px tabs and labeled's 46px
    // row tabs instead of overflowing past the bar edge on those variants.
    indicator.style.top = (tabRect.top - barRect.top - borderTop) + 'px';
    indicator.style.height = tabRect.height + 'px';
  }

  function boot() {
    bindAllSurfaces(document);
    positionIndicator();

    var mo = new MutationObserver(function (mutations) {
      var needsBind = false;
      mutations.forEach(function (m) {
        m.addedNodes && m.addedNodes.forEach(function (node) {
          if (node.nodeType === 1) needsBind = true;
        });
      });
      if (needsBind) bindAllSurfaces(document);
      positionIndicator();
    });
    mo.observe(document.body, { childList: true, subtree: true });

    window.addEventListener('resize', positionIndicator);
    document.addEventListener('fomoji-appearance-change', positionIndicator);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
