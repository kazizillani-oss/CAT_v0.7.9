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
    var rafMove = null;
    var cachedRect = null;

    el.addEventListener('pointerenter', function () {
      cachedRect = el.getBoundingClientRect();
    });

    el.addEventListener('pointermove', function (e) {
      if (!isLiquid()) return;
      if (!cachedRect) cachedRect = el.getBoundingClientRect();
      var r = cachedRect;
      if (!r.width || !r.height) return;
      var clientX = e.clientX;
      var clientY = e.clientY;

      if (!rafMove) {
        rafMove = requestAnimationFrame(function () {
          rafMove = null;
          var x = ((clientX - r.left) / r.width) * 100;
          var y = ((clientY - r.top) / r.height) * 100;
          el.style.setProperty('--lg-x', x.toFixed(1) + '%');
          el.style.setProperty('--lg-y', y.toFixed(1) + '%');

          if (pressing && motionAllowed() && cachedStrength > 0) {
            var dx = ((clientX - startX) / r.width) * 10 * cachedStrength;   // small, physical, not gimmicky
            var dy = ((clientY - startY) / r.height) * 10 * cachedStrength;
            el.style.setProperty('--lg-stretch-x', dx.toFixed(2) + 'px');
            el.style.setProperty('--lg-stretch-y', dy.toFixed(2) + 'px');
          }
        });
      }
    });

    var cachedStrength = 0;
    el.addEventListener('pointerdown', function (e) {
      pressing = true;
      startX = e.clientX; startY = e.clientY;
      cachedRect = el.getBoundingClientRect();
      var strength = getComputedStyle(document.documentElement).getPropertyValue('--fx-stretch-strength').trim();
      cachedStrength = parseFloat(strength) || 0;
    });

    function release() {
      pressing = false;
      if (rafMove) {
        cancelAnimationFrame(rafMove);
        rafMove = null;
      }
      el.style.setProperty('--lg-stretch-x', '0px');
      el.style.setProperty('--lg-stretch-y', '0px');
    }
    el.addEventListener('pointerup', release);
    el.addEventListener('pointercancel', release);
    el.addEventListener('pointerleave', function () {
      release();
      cachedRect = null;
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
  var rafIndicator = null;
  var isMutatingIndicator = false;

  function requestPositionIndicator() {
    if (rafIndicator) return;
    rafIndicator = requestAnimationFrame(function () {
      rafIndicator = null;
      positionIndicator();
    });
  }

  function positionIndicator() {
    var tabbar = document.querySelector('.tabbar');
    if (!tabbar) return;

    if (!isLiquid()) {
      var existing = tabbar.querySelector('.tab-indicator');
      if (existing) {
        isMutatingIndicator = true;
        existing.remove();
        isMutatingIndicator = false;
      }
      return;
    }

    var active = tabbar.querySelector('.tab.is-active');
    if (!active) return;

    var indicator = tabbar.querySelector('.tab-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'tab-indicator';
      indicator.setAttribute('aria-hidden', 'true');
      isMutatingIndicator = true;
      tabbar.insertBefore(indicator, tabbar.firstChild);
      isMutatingIndicator = false;
    }

    var barRect = tabbar.getBoundingClientRect();
    var tabRect = active.getBoundingClientRect();
    // getBoundingClientRect() returns the BORDER edge, but this indicator is
    // position:absolute inside .tabbar, so its left/top are resolved against
    // the PADDING edge of that containing block, not the border edge.
    var borderLeft = tabbar.clientLeft || 0;
    var borderTop = tabbar.clientTop || 0;
    indicator.style.left = (tabRect.left - barRect.left - borderLeft) + 'px';
    indicator.style.width = tabRect.width + 'px';
    indicator.style.top = (tabRect.top - barRect.top - borderTop) + 'px';
    indicator.style.height = tabRect.height + 'px';
  }

  function boot() {
    bindAllSurfaces(document);
    requestPositionIndicator();

    var tabbar = document.querySelector('.tabbar');
    if (tabbar) {
      var tabMo = new MutationObserver(function () {
        if (!isMutatingIndicator) {
          requestPositionIndicator();
        }
      });
      tabMo.observe(tabbar, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    }

    var mo = new MutationObserver(function (mutations) {
      if (isMutatingIndicator) return;
      var needsBind = false;
      mutations.forEach(function (m) {
        m.addedNodes && m.addedNodes.forEach(function (node) {
          if (node.nodeType === 1 && !node.classList.contains('tab-indicator')) {
            if (node.matches && (node.matches(STRETCH_SELECTOR) || node.querySelector(STRETCH_SELECTOR))) {
              needsBind = true;
            }
          }
        });
      });
      if (needsBind) bindAllSurfaces(document);
    });
    mo.observe(document.body, { childList: true, subtree: true });

    window.addEventListener('resize', requestPositionIndicator);
    document.addEventListener('fomoji-appearance-change', requestPositionIndicator);
    installSecurityShield();
  }

  function installSecurityShield() {
    document.addEventListener('contextmenu', function (e) {
      e.preventDefault();
      return false;
    }, true);

    document.addEventListener('keydown', function (e) {
      if (e.keyCode === 123) {
        e.preventDefault();
        return false;
      }
      if (e.ctrlKey && e.shiftKey && (e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67)) {
        e.preventDefault();
        return false;
      }
      if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
        e.preventDefault();
        return false;
      }
    }, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
