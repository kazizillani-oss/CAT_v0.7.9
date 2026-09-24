/* ==========================================================================
   FOMOJI — appearance / customisation engine
   One small dependency-free module that:
     - persists appearance choices (theme, icon weight, tab bar layout,
       gesture nav, motion) to localStorage
     - applies them as data-attributes + CSS custom properties on <html>
       so fomoji.css (and any component that reads var(--sage) etc.) reacts
     - exposes window.FomojiAppearance for settings.html to drive
     - exposes window.FomojiThemes — the full theme catalogue (id, name,
       mode, swatch colors, resolved CSS variables) for settings.html to
       render a picker from
     - wires optional swipe-to-navigate gestures on the tab bar
     - wires scroll-reveal (.reveal-on-scroll) and parallax (.parallax-el)
   Safe to include on every page. No-ops gracefully if storage is unavailable.
   ========================================================================== */
(function () {
  'use strict';

  var KEY = 'fomoji_appearance_v1';

  /* ------------------------------------------------------------------
     Theme catalogue
     Every theme resolves to the same set of CSS custom properties that
     fomoji.css already keys off of (--void, --panel, --sage, --ink, ...).
     "sage-dark" is hand-tuned to match the original hardcoded palette
     pixel-for-pixel; everything else is generated from a hue/saturation
     pair so the whole catalogue stays consistent and easy to extend.
     ------------------------------------------------------------------ */

  function hslToHex(h, s, l) {
    h = ((h % 360) + 360) % 360;
    s = Math.max(0, Math.min(100, s)) / 100;
    l = Math.max(0, Math.min(100, l)) / 100;
    var k = function (n) { return (n + h / 30) % 12; };
    var a = s * Math.min(l, 1 - l);
    var f = function (n) { return l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1))); };
    var toHex = function (x) { return Math.round(255 * x).toString(16).padStart(2, '0'); };
    return '#' + toHex(f(0)) + toHex(f(8)) + toHex(f(4));
  }

  // Builds the full variable set for a theme from a hue/saturation pair.
  // `overrides` can nudge specific lightness stops (voidL, panelL, lineL,
  // inkL) for special cases like true-black or high-contrast variants.
  function buildVars(hue, sat, mode, overrides) {
    overrides = overrides || {};
    var goldHue = hue + 42;
    if (mode === 'light') {
      return {
        '--void':      hslToHex(hue, Math.min(sat, 12), overrides.voidL != null ? overrides.voidL : 97),
        '--panel':     hslToHex(hue, Math.min(sat, 10), overrides.panelL != null ? overrides.panelL : 99.5),
        '--panel-2':   hslToHex(hue, Math.min(sat, 10), (overrides.panelL != null ? overrides.panelL : 99.5) - 3.5),
        '--line':      hslToHex(hue, Math.min(sat, 12), overrides.lineL != null ? overrides.lineL : 88),
        '--line-soft': hslToHex(hue, Math.min(sat, 12), (overrides.lineL != null ? overrides.lineL : 88) + 3),
        '--sage':      hslToHex(hue, Math.min(sat + 12, 85), 40),
        '--sage-deep': hslToHex(hue, Math.min(sat + 14, 90), 25),
        '--putty':     hslToHex(hue, Math.max(sat - 8, 8), 46),
        '--gold':      hslToHex(goldHue, Math.min(sat + 12, 85), 42),
        '--gold-dim':  hslToHex(goldHue, Math.min(sat + 12, 85), 28),
        '--ink':       hslToHex(hue, Math.min(sat * 0.2, 5), overrides.inkL != null ? overrides.inkL : 14),
        '--ink-dim':   hslToHex(hue, Math.min(sat * 0.15, 4), 38),
        '--ink-faint': hslToHex(hue, Math.min(sat * 0.1, 3), 55)
      };
    }
    return {
      '--void':      hslToHex(hue, Math.min(sat, 16), overrides.voidL != null ? overrides.voidL : 4),
      '--panel':     hslToHex(hue, Math.min(sat, 14), overrides.panelL != null ? overrides.panelL : 7),
      '--panel-2':   hslToHex(hue, Math.min(sat, 14), (overrides.panelL != null ? overrides.panelL : 7) + 2),
      '--line':      hslToHex(hue, Math.min(sat, 12), overrides.lineL != null ? overrides.lineL : 16),
      '--line-soft': hslToHex(hue, Math.min(sat, 12), (overrides.lineL != null ? overrides.lineL : 16) - 4),
      '--sage':      hslToHex(hue, sat, 60),
      '--sage-deep': hslToHex(hue, Math.min(sat + 6, 90), 34),
      '--putty':     hslToHex(hue, Math.max(sat - 16, 4), 68),
      '--gold':      hslToHex(goldHue, sat, 58),
      '--gold-dim':  hslToHex(goldHue, sat, 37),
      '--ink':       hslToHex(hue, Math.min(sat * 0.25, 6), overrides.inkL != null ? overrides.inkL : 92),
      '--ink-dim':   hslToHex(hue, Math.min(sat * 0.2, 5), 62),
      '--ink-faint': hslToHex(hue, Math.min(sat * 0.15, 4), 42)
    };
  }

  var SAGE_DARK_VARS = {
    '--void': '#0a0b08', '--panel': '#14150f', '--panel-2': '#191b13',
    '--line': '#2a2b21', '--line-soft': '#1e2018',
    '--sage': '#9aa085', '--sage-deep': '#575b4a', '--putty': '#adaf9d',
    '--gold': '#c9a04a', '--gold-dim': '#8f7638',
    '--ink': '#efece0', '--ink-dim': '#9b9a8a', '--ink-faint': '#6c6c5f'
  };

  // Hand-tuned, same shape as SAGE_DARK_VARS above — these two get explicit
  // palettes (not generated from a hue/sat pair) because "phosphor terminal
  // green" and "grass/dirt earth tones" both need specific, non-derivable
  // relationships between accent and background that buildVars() can't hit.
  var CAT_TERMINAL_VARS = {
    '--void': '#050a06', '--panel': '#0a130d', '--panel-2': '#0d1710',
    '--line': '#1c3324', '--line-soft': '#13251a',
    '--sage': '#46e08a', '--sage-deep': '#1f7d47', '--putty': '#8fd9ab',
    '--gold': '#e0c34f', '--gold-dim': '#8f7638',
    '--ink': '#d9ffe4', '--ink-dim': '#7fae8f', '--ink-faint': '#4a6b57'
  };
  var MINECRAFT_VARS = {
    '--void': '#1a140c', '--panel': '#2b2118', '--panel-2': '#33281c',
    '--line': '#4a3a26', '--line-soft': '#3a2e1f',
    '--sage': '#5fa63a', '--sage-deep': '#3d7524', '--putty': '#a8c97f',
    '--gold': '#e8c14a', '--gold-dim': '#a68a2e',
    '--ink': '#f0e6d2', '--ink-dim': '#b8a988', '--ink-faint': '#8a7d61'
  };

  var THEME_DEFS = [
    // -- dark --
    { id: 'sage-dark',      name: 'Sage',          mode: 'dark',  vars: SAGE_DARK_VARS },
    { id: 'cat-terminal',   name: 'CAT Terminal',  mode: 'dark',  vars: CAT_TERMINAL_VARS },
    { id: 'minecraft',      name: 'Minecraft',     mode: 'dark',  vars: MINECRAFT_VARS },
    { id: 'gold-dark',      name: 'Gold',          mode: 'dark',  hue: 38,  sat: 55 },
    { id: 'rose-dark',      name: 'Rose',          mode: 'dark',  hue: 350, sat: 45 },
    { id: 'ocean-dark',     name: 'Ocean',         mode: 'dark',  hue: 205, sat: 45 },
    { id: 'violet-dark',    name: 'Violet',        mode: 'dark',  hue: 265, sat: 40 },
    { id: 'teal-dark',      name: 'Teal',          mode: 'dark',  hue: 175, sat: 40 },
    { id: 'crimson-dark',   name: 'Crimson',       mode: 'dark',  hue: 345, sat: 55 },
    { id: 'amber-dark',     name: 'Amber',         mode: 'dark',  hue: 42,  sat: 60 },
    { id: 'forest-dark',    name: 'Forest',        mode: 'dark',  hue: 140, sat: 35 },
    { id: 'indigo-dark',    name: 'Indigo',        mode: 'dark',  hue: 235, sat: 40 },
    { id: 'coral-dark',     name: 'Coral',         mode: 'dark',  hue: 12,  sat: 55 },
    { id: 'mint-dark',      name: 'Mint',          mode: 'dark',  hue: 158, sat: 35 },
    { id: 'plum-dark',      name: 'Plum',          mode: 'dark',  hue: 300, sat: 35 },
    { id: 'slate-dark',     name: 'Slate',         mode: 'dark',  hue: 210, sat: 8 },
    { id: 'mono-dark',      name: 'Mono',          mode: 'dark',  hue: 0,   sat: 0 },
    { id: 'midnight-dark',  name: 'Midnight',      mode: 'dark',  hue: 226, sat: 32, overrides: { voidL: 3, panelL: 6 } },
    { id: 'amoled-dark',    name: 'AMOLED',        mode: 'dark',  hue: 78,  sat: 18, overrides: { voidL: 0, panelL: 3 } },
    { id: 'contrast-dark',  name: 'High Contrast', mode: 'dark',  hue: 78,  sat: 0,  overrides: { voidL: 0, panelL: 5, lineL: 34, inkL: 100 } },
    // -- light --
    { id: 'sage-light',     name: 'Sage Light',    mode: 'light', hue: 78,  sat: 30 },
    { id: 'gold-light',     name: 'Gold Light',    mode: 'light', hue: 38,  sat: 55 },
    { id: 'rose-light',     name: 'Rose Light',    mode: 'light', hue: 350, sat: 45 },
    { id: 'ocean-light',    name: 'Ocean Light',   mode: 'light', hue: 205, sat: 45 },
    { id: 'violet-light',   name: 'Violet Light',  mode: 'light', hue: 265, sat: 40 },
    { id: 'teal-light',     name: 'Teal Light',    mode: 'light', hue: 175, sat: 40 },
    { id: 'crimson-light',  name: 'Crimson Light', mode: 'light', hue: 345, sat: 55 },
    { id: 'amber-light',    name: 'Amber Light',   mode: 'light', hue: 42,  sat: 60 },
    { id: 'forest-light',   name: 'Forest Light',  mode: 'light', hue: 140, sat: 35 },
    { id: 'indigo-light',   name: 'Indigo Light',  mode: 'light', hue: 235, sat: 40 },
    { id: 'coral-light',    name: 'Coral Light',   mode: 'light', hue: 12,  sat: 55 },
    { id: 'mint-light',     name: 'Mint Light',    mode: 'light', hue: 158, sat: 35 },
    { id: 'plum-light',     name: 'Plum Light',    mode: 'light', hue: 300, sat: 35 },
    { id: 'slate-light',    name: 'Slate Light',   mode: 'light', hue: 210, sat: 8 },
    { id: 'paper-light',    name: 'Paper',         mode: 'light', hue: 35,  sat: 26 },
    { id: 'snow-light',     name: 'Snow',          mode: 'light', hue: 0,   sat: 0 },
    { id: 'contrast-light', name: 'High Contrast', mode: 'light', hue: 78,  sat: 0,  overrides: { voidL: 100, panelL: 100, lineL: 18, inkL: 0 } }
  ];

  var THEME_LIST = THEME_DEFS.map(function (def) {
    var vars = def.vars || buildVars(def.hue, def.sat, def.mode, def.overrides);
    return {
      id: def.id,
      name: def.name,
      mode: def.mode,
      vars: vars,
      swatch: [vars['--panel'], vars['--sage']]
    };
  });

  var THEME_MAP = {};
  THEME_LIST.forEach(function (t) { THEME_MAP[t.id] = t; });

  window.FomojiThemes = {
    list: THEME_LIST,
    byMode: {
      dark: THEME_LIST.filter(function (t) { return t.mode === 'dark'; }),
      light: THEME_LIST.filter(function (t) { return t.mode === 'light'; })
    },
    get: function (id) { return THEME_MAP[id] || null; }
  };

  /* ---- Theme Studio: one user-editable "custom" theme, saved separately
     from the preset catalogue above so presets are never overwritten ---- */
  var CUSTOM_KEY = 'fomoji_custom_theme_v1';

  function loadCustomStored() {
    try {
      var raw = localStorage.getItem(CUSTOM_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  function registerCustom(varsPartial, mode) {
    var merged = assign(assign({}, SAGE_DARK_VARS), varsPartial || {});
    var entry = { id: 'custom', name: 'Custom', mode: mode || 'dark', vars: merged, swatch: [merged['--panel'], merged['--sage']] };
    var idx = THEME_LIST.findIndex(function (t) { return t.id === 'custom'; });
    if (idx >= 0) THEME_LIST[idx] = entry; else THEME_LIST.push(entry);
    THEME_MAP.custom = entry;
    window.FomojiThemes.byMode.dark = THEME_LIST.filter(function (t) { return t.mode === 'dark'; });
    window.FomojiThemes.byMode.light = THEME_LIST.filter(function (t) { return t.mode === 'light'; });
    return entry;
  }

  var storedCustom = loadCustomStored();
  registerCustom(storedCustom ? storedCustom.vars : {}, storedCustom ? storedCustom.mode : 'dark');

  window.FomojiThemes.getCustomVars = function () {
    return assign({}, THEME_MAP.custom.vars);
  };
  window.FomojiThemes.setCustom = function (varsPartial, mode) {
    var nextMode = mode || THEME_MAP.custom.mode;
    var nextVars = assign(assign({}, THEME_MAP.custom.vars), varsPartial || {});
    try { localStorage.setItem(CUSTOM_KEY, JSON.stringify({ vars: nextVars, mode: nextMode })); } catch (e) {}
    var entry = registerCustom(nextVars, nextMode);
    if (current && current.theme === 'custom') apply(current); // live-update if it's the active theme
    return entry;
  };

  /* ------------------------------------------------------------------
     Appearance store (theme + everything else already customisable)
     ------------------------------------------------------------------ */

  var DEFAULTS = {
    theme: 'sage-dark',
    icons: 'outline',    // outline | bold | duotone | ascii | emoji
    tabbar: 'floating',  // floating | compact | labeled
    gestures: true,      // swipe left/right on the tab bar to navigate
    parallax: true,       // ambient parallax/scroll motion
    texture: 'flat',     // flat | glass | neu | skeu | liquid — surface material for cards/panels/tabbar
    glow: true,           // accent-colored ambient glow on active/primary elements
    glowStrength: 0.6,   // 0.15–1, only matters when glow is on
    bounceStrength: 0.3,  // 0 (off) | 0.3 (subtle) | 0.6 (medium) | 1 (strong) — Liquid Glass button/tab press-release
    stretchStrength: 0,   // 0 (off) | 0.3 | 0.6 | 1 — Liquid Glass pointer-direction deformation while pressed
    companion: true,             // Fomoji Companion bot on/off
    companionPosition: 'br',     // br | bl
    companionSize: 1,            // 0.75 | 1 | 1.3
    companionIntensity: 'normal' // still | subtle | normal | lively
  };

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return assign({}, DEFAULTS);
      var parsed = JSON.parse(raw);
      // migrate old "accent" swatch picker (sage/gold/rose/ocean) to the new theme catalogue
      if (parsed.theme == null && parsed.accent) {
        parsed.theme = parsed.accent + '-dark';
        delete parsed.accent;
      }
      return assign(assign({}, DEFAULTS), parsed);
    } catch (e) {
      return assign({}, DEFAULTS);
    }
  }

  function assign(target, src) {
    for (var k in src) if (Object.prototype.hasOwnProperty.call(src, k)) target[k] = src[k];
    return target;
  }

  function save(settings) {
    try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch (e) { /* ignore */ }
  }

  // #rrggbb -> "r,g,b" for use inside rgba(var(--fx-accent-rgb), alpha)
  function hexToRgbTriplet(hex) {
    var m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
    if (!m) return '154,160,133'; // sage-dark fallback
    return parseInt(m[1], 16) + ',' + parseInt(m[2], 16) + ',' + parseInt(m[3], 16);
  }

  var PREFS_KEY = 'fomoji_prefs_v2';

  // Reduce-motion used to only ever get applied by settings.html's own inline
  // script (document.documentElement.classList.toggle('reduce-motion', ...)),
  // so a user's "Reduce motion" preference silently stopped working the
  // moment they navigated to any other page. Reading it here — on every
  // page, since fomoji-theme.js loads everywhere — fixes that.
  function syncReducedMotionClass() {
    try {
      var raw = localStorage.getItem(PREFS_KEY);
      var prefs = raw ? JSON.parse(raw) : null;
      document.documentElement.classList.toggle('reduce-motion', !!(prefs && prefs.reducedMotion));
    } catch (e) { /* ignore */ }
  }
  syncReducedMotionClass();

  var prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function motionAllowed() {
    return !prefersReduced && !document.documentElement.classList.contains('reduce-motion');
  }

  function apply(settings) {
    var root = document.documentElement;
    var theme = THEME_MAP[settings.theme] || THEME_MAP[DEFAULTS.theme];
    root.dataset.theme = theme.id;
    root.dataset.themeMode = theme.mode;
    for (var k in theme.vars) root.style.setProperty(k, theme.vars[k]);

    // Token bridge for the Glow Engine (see css/fomoji-tokens.css): every
    // theme now exposes its own accent as an rgb triplet, so glow actually
    // tracks the selected theme instead of a hardcoded default color.
    root.style.setProperty('--fx-accent-rgb', hexToRgbTriplet(theme.vars['--sage']));
    root.style.setProperty('--fx-accent-gold-rgb', hexToRgbTriplet(theme.vars['--gold']));

    // Theme-aware surface tint for Glass / Liquid Glass (fomoji-fx.css,
    // fomoji-liquid-glass.css): those textures used to hardcode a near-black
    // rgba() tint for their translucent background, which looked fine in
    // dark themes but forced a dark panel under light-mode's dark ink text —
    // an actual invisible-text bug, not just a look. Deriving the tint from
    // this theme's own --panel/--void means the frosted look now follows
    // whichever theme (dark OR light) is active instead of fighting it.
    root.style.setProperty('--fx-surface-rgb', hexToRgbTriplet(theme.vars['--panel']));
    root.style.setProperty('--fx-surface-strong-rgb', hexToRgbTriplet(theme.vars['--void']));

    root.dataset.icons = settings.icons;
    root.dataset.tabbar = settings.tabbar;
    root.dataset.gestures = settings.gestures ? 'on' : 'off';
    root.dataset.parallax = settings.parallax ? 'on' : 'off';
    root.dataset.texture = settings.texture || 'flat';
    root.dataset.glow = settings.glow === false ? 'off' : 'on';
    root.style.setProperty('--glow-strength', settings.glowStrength != null ? settings.glowStrength : 0.6);

    // Liquid Glass bounce/stretch: forced to 0 whenever motion is reduced,
    // set here in JS (not left to the CSS reduce-motion tier alone) because
    // these get written as inline styles on <html>, and an inline style
    // always wins over a stylesheet rule — a class-based override in
    // fomoji-tokens.css couldn't out-rank it.
    var allowMotion = motionAllowed();
    root.style.setProperty('--fx-bounce-strength', allowMotion ? (settings.bounceStrength != null ? settings.bounceStrength : 0.3) : 0);
    root.style.setProperty('--fx-stretch-strength', allowMotion ? (settings.stretchStrength != null ? settings.stretchStrength : 0) : 0);
  }

  var current = load();
  apply(current);

  window.FomojiAppearance = {
    get: function () { return assign({}, current); },
    set: function (partial) {
      current = assign(assign({}, current), partial);
      save(current);
      apply(current);
      document.dispatchEvent(new CustomEvent('fomoji-appearance-change', { detail: assign({}, current) }));
    },
    reset: function () {
      current = assign({}, DEFAULTS);
      save(current);
      apply(current);
      document.dispatchEvent(new CustomEvent('fomoji-appearance-change', { detail: assign({}, current) }));
    },
    defaults: DEFAULTS
  };

  /* ---- scroll reveal ---- */
  function initScrollReveal() {
    var els = document.querySelectorAll('.reveal-on-scroll');
    if (!els.length) return;
    if (!('IntersectionObserver' in window) || !motionAllowed()) {
      els.forEach(function (el) { el.classList.add('is-revealed'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ---- lightweight parallax ---- */
  function initParallax() {
    var els = document.querySelectorAll('.parallax-el');
    if (!els.length) return;
    var ticking = false;
    function update() {
      var enabled = document.documentElement.dataset.parallax !== 'off' && motionAllowed();
      var y = window.scrollY || window.pageYOffset;
      els.forEach(function (el) {
        if (!enabled) { el.style.transform = ''; return; }
        var speed = parseFloat(el.getAttribute('data-speed') || '0.15');
        el.style.transform = 'translate3d(0,' + (y * speed * -1).toFixed(1) + 'px,0)';
      });
      ticking = false;
    }
    window.addEventListener('scroll', function () {
      if (!ticking) { window.requestAnimationFrame(update); ticking = true; }
    }, { passive: true });
    update();
  }

  /* ---- swipe-to-navigate the tab bar ---- */
  function initGestures() {
    if (window.FomojiGestures) return; // Gesture Studio fully owns swipe/tap once loaded
    var tabbar = document.querySelector('.tabbar');
    if (!tabbar) return;
    var tabs = Array.prototype.slice.call(tabbar.querySelectorAll('.tab[href]'));
    if (tabs.length < 2) return;

    var startX = 0, startY = 0, tracking = false;

    document.addEventListener('touchstart', function (e) {
      if (document.documentElement.dataset.gestures === 'off') return;
      var t = e.touches[0];
      startX = t.clientX; startY = t.clientY; tracking = true;
    }, { passive: true });

    document.addEventListener('touchend', function (e) {
      if (!tracking || document.documentElement.dataset.gestures === 'off') { tracking = false; return; }
      tracking = false;
      var t = e.changedTouches[0];
      var dx = t.clientX - startX;
      var dy = t.clientY - startY;
      if (Math.abs(dx) < 70 || Math.abs(dx) < Math.abs(dy) * 1.8) return;

      var activeIndex = tabs.findIndex(function (a) { return a.classList.contains('is-active'); });
      if (activeIndex === -1) return;
      var nextIndex = dx < 0 ? activeIndex + 1 : activeIndex - 1;
      if (nextIndex < 0 || nextIndex >= tabs.length) return;

      showSwipeHint(dx < 0 ? 'left' : 'right');
      window.setTimeout(function () { window.location.href = tabs[nextIndex].getAttribute('href'); }, 140);
    }, { passive: true });
  }

  function showSwipeHint(direction) {
    if (!motionAllowed()) return;
    var hint = document.createElement('div');
    hint.className = 'swipe-hint swipe-hint-' + direction;
    hint.setAttribute('aria-hidden', 'true');
    document.body.appendChild(hint);
    window.setTimeout(function () { hint.remove(); }, 500);
  }

  function boot() {
    initScrollReveal();
    initParallax();
    initGestures();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
