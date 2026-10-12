/* ==========================================================================
   FOMOJI — 3D Depth Engine controller (spec sections 14-17)

   Small, dependency-free companion to css/fomoji-3d.css:
     - reads/writes a `depth3d` field on the existing window.FomojiAppearance
       store (fomoji-theme.js) so it lives alongside every other appearance
       setting instead of a second localStorage key
     - applies it as data-depth3d on <html>, LOW/MEDIUM/HIGH/OFF (spec
       section 16)
     - optional per-card pointer tilt for elements marked
       data-tilt="pointer" (everything else gets the CSS-only symmetric
       hover tilt — no JS required for the baseline effect)
     - pauses .fx-float-el ambient animations when off-screen
       (IntersectionObserver) or under prefers-reduced-motion (spec
       section 17)

   Load after fomoji-theme.js. No-ops gracefully if FomojiAppearance isn't
   present yet (still applies a sane default from localStorage directly).
   ========================================================================== */
(function () {
  'use strict';

  var DEPTH_LEVELS = ['off', 'low', 'medium', 'high'];
  var DEFAULT_DEPTH = 'medium';

  function motionAllowed() {
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    return !reduced && !document.documentElement.classList.contains('reduce-motion');
  }

  function currentDepth() {
    var stored = null;
    if (window.FomojiAppearance) stored = window.FomojiAppearance.get().depth3d;
    if (!stored) {
      try {
        var raw = localStorage.getItem('fomoji_depth3d_v1');
        if (raw) stored = raw;
      } catch (e) { /* ignore */ }
    }
    return DEPTH_LEVELS.indexOf(stored) >= 0 ? stored : DEFAULT_DEPTH;
  }

  function applyDepth(level) {
    var safe = DEPTH_LEVELS.indexOf(level) >= 0 ? level : DEFAULT_DEPTH;
    document.documentElement.dataset.depth3d = motionAllowed() ? safe : (safe === 'off' ? 'off' : 'low');
  }

  window.FomojiDepth3D = {
    levels: DEPTH_LEVELS.slice(),
    get: currentDepth,
    set: function (level) {
      if (DEPTH_LEVELS.indexOf(level) < 0) return;
      if (window.FomojiAppearance) {
        window.FomojiAppearance.set({ depth3d: level });
      } else {
        try { localStorage.setItem('fomoji_depth3d_v1', level); } catch (e) { /* ignore */ }
        applyDepth(level);
      }
    },
  };

  applyDepth(currentDepth());
  document.addEventListener('fomoji-appearance-change', function (e) {
    if (e.detail && e.detail.depth3d) applyDepth(e.detail.depth3d);
  });

  /* ---- optional pointer-tilt for data-tilt="pointer" cards ---- */
  function initPointerTilt() {
    if (!motionAllowed()) return;
    var els = document.querySelectorAll('.card-3d[data-tilt="pointer"]');
    els.forEach(function (el) {
      var rect = null;
      var maxTilt = 7;
      var rafId = null;
      var targetX = 0;
      var targetY = 0;

      function updateTilt() {
        rafId = null;
        el.style.setProperty('--tilt-x', targetX.toFixed(2) + 'deg');
        el.style.setProperty('--tilt-y', targetY.toFixed(2) + 'deg');
      }

      el.addEventListener('pointerenter', function () {
        rect = el.getBoundingClientRect();
        maxTilt = parseFloat(getComputedStyle(el).getPropertyValue('--fx-depth-tilt')) || 7;
        el.style.transition = 'transform 0s linear, box-shadow var(--fx-duration-slow) var(--fx-ease-decel)';
      });

      el.addEventListener('pointermove', function (e) {
        if (!rect) {
          rect = el.getBoundingClientRect();
          maxTilt = parseFloat(getComputedStyle(el).getPropertyValue('--fx-depth-tilt')) || 7;
        }
        var rawPx = (e.clientX - rect.left) / (rect.width || 1) - 0.5;
        var rawPy = (e.clientY - rect.top) / (rect.height || 1) - 0.5;
        var px = Math.max(-0.5, Math.min(0.5, rawPx));
        var py = Math.max(-0.5, Math.min(0.5, rawPy));
        targetX = Math.max(-maxTilt * 2, Math.min(maxTilt * 2, -py * maxTilt * 2));
        targetY = Math.max(-maxTilt * 2, Math.min(maxTilt * 2, px * maxTilt * 2));
        if (!rafId) {
          rafId = requestAnimationFrame(updateTilt);
        }
      });

      el.addEventListener('pointerleave', function () {
        if (rafId) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
        rect = null;
        el.style.transition = '';
        el.style.setProperty('--tilt-x', '0deg');
        el.style.setProperty('--tilt-y', '0deg');
      });
    });
  }

  /* ---- pause floating/ambient animation when off-screen ---- */
  function initVisibilityPause() {
    var els = document.querySelectorAll('.fx-float-el');
    if (!els.length || !('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        entry.target.classList.toggle('fx-3d-paused', !entry.isIntersecting);
      });
    }, { threshold: 0.01 });
    els.forEach(function (el) { io.observe(el); });
  }

  function boot() {
    initPointerTilt();
    initVisibilityPause();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
