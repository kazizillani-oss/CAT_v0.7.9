/* ==========================================================================
   FOMOJI — AnimatedBot (single consolidated companion engine)

   Replaces the two bot systems that used to run at once (fomoji-bot.js +
   fomoji-companion.js — the "two floating bots" bug). There is now exactly
   ONE renderer, ONE state object, ONE DOM node, ONE animation controller.
   Adding a look means adding an entry to BOT_THEMES, never a new file or
   a second instance.

   Independence contract: this module never touches login, registration,
   WebAuthn/passkeys, session handling, sign-out, or CAT connection, and
   nothing in the rest of the app requires it to function. If this file
   fails to load or throws, everything else keeps working. The optional
   FomojiSignOut hook below is a one-way, best-effort, non-blocking call.

   Public API: window.AnimatedBot
     get() / set(partial) / reset() / react(state, opts?)
     THEMES, FACES, EYES, DEPTHS, POSITIONS, SIZES
   Back-compat shims (so index.html / signup.html don't need edits):
     window.FomojiCompanion = { react(state), mountPreview(el) }
   ========================================================================== */
(function () {
  'use strict';

  if (window.AnimatedBot) return;

  var KEY = 'fomoji_animated_bot_v1';

  /* ------------------------------------------------------------------
     Theme catalogue — 35 presets, one shared engine. Each entry is just
     colors + a texture tag; the CSS in fomoji-animated-bot.css does the
     actual rendering per texture family (flat / 3d / emoji / pixel /
     glass / neu / skeu / crystal / holo / cyber / quantum / scientific /
     crt / metallic / arcade / retro / cat), so 35 presets never means 35
     bot implementations.
     ------------------------------------------------------------------ */
  var BOT_THEMES = [
    { id: 'classic',        name: 'Classic Fomoji', group: 'Fomoji',   texture: 'flat',      depth: 'low',    vars: { primary: '#46e08a', secondary: '#1f7d47', edge: '#163d26', glow: 'rgba(70,224,138,0.5)', eyeBg: '#04140b', pupil: '#d9ffe4' } },
    { id: 'fomojiGreen',    name: 'Fomoji Green',   group: 'Fomoji',   texture: 'flat',      depth: 'low',    vars: { primary: '#2ecc71', secondary: '#145a32', edge: '#0d3a20', glow: 'rgba(46,204,113,0.5)', eyeBg: '#052411', pupil: '#eafff1' } },
    { id: 'minimal',        name: 'Minimal',        group: 'Fomoji',   texture: 'flat',      depth: 'off',    vars: { primary: '#e7e7e2', secondary: '#f4f4f0', edge: '#c9c9c1', glow: 'rgba(0,0,0,0.12)', eyeBg: '#232320', pupil: '#f4f4f0' } },
    { id: 'minimalDark',    name: 'Minimal Dark',   group: 'Fomoji',   texture: 'flat',      depth: 'off',    vars: { primary: '#232323', secondary: '#2e2e2e', edge: '#3a3a3a', glow: 'rgba(255,255,255,0.1)', eyeBg: '#111', pupil: '#eee' } },
    { id: '3d',             name: '3D',             group: '3D',       texture: '3d',        depth: 'medium', vars: { primary: '#6c8cff', secondary: '#3a53c4', edge: '#24306e', glow: 'rgba(108,140,255,0.5)', eyeBg: '#0d1230', pupil: '#e6ecff' } },
    { id: '3dSoft',         name: '3D Soft',        group: '3D',       texture: '3d',        depth: 'low',    vars: { primary: '#ffb199', secondary: '#d97a5f', edge: '#8a4632', glow: 'rgba(255,177,153,0.45)', eyeBg: '#4a2318', pupil: '#fff0ea' } },
    { id: '3dGlossy',       name: '3D Glossy',      group: '3D',       texture: '3d-glossy',  depth: 'high',   vars: { primary: '#48c6ef', secondary: '#2380a6', edge: '#145066', glow: 'rgba(72,198,239,0.55)', eyeBg: '#052733', pupil: '#eafcff' } },
    { id: '3dMetallic',     name: '3D Metallic',    group: '3D',       texture: 'metallic',   depth: 'high',   vars: { primary: '#c7ccd1', secondary: '#8b9096', edge: '#52565b', glow: 'rgba(255,255,255,0.35)', eyeBg: '#26282b', pupil: '#fff' } },
    { id: 'emoji',          name: 'Emoji',          group: 'Emoji',    texture: 'emoji',      depth: 'low',    vars: { primary: '#ffd34d', secondary: '#ffb800', edge: '#a97a00', glow: 'rgba(255,211,77,0.5)', eyeBg: '#241a00', pupil: '#241a00' } },
    { id: 'emojiSoft',      name: 'Emoji Soft',     group: 'Emoji',    texture: 'emoji',      depth: 'low',    vars: { primary: '#ffe8b0', secondary: '#ffcf7a', edge: '#c99a3f', glow: 'rgba(255,232,176,0.5)', eyeBg: '#4a3a12', pupil: '#4a3a12' } },
    { id: 'emojiGlossy',    name: 'Emoji Glossy',   group: 'Emoji',    texture: '3d-glossy',  depth: 'medium', vars: { primary: '#ffdf6b', secondary: '#ffb020', edge: '#8a5a00', glow: 'rgba(255,223,107,0.6)', eyeBg: '#2b1c00', pupil: '#2b1c00' } },
    { id: 'emojiDark',      name: 'Emoji Dark',     group: 'Emoji',    texture: 'emoji',      depth: 'low',    vars: { primary: '#4a4636', secondary: '#2c2a20', edge: '#1a1912', glow: 'rgba(255,211,77,0.3)', eyeBg: '#efe4c0', pupil: '#1a1912' } },
    { id: 'cat',            name: 'CAT',            group: 'CAT',      texture: 'cat',        depth: 'low',    vars: { primary: '#46e08a', secondary: '#1f7d47', edge: '#123d24', glow: 'rgba(70,224,138,0.5)', eyeBg: '#04100a', pupil: '#d9ffe4' } },
    { id: 'catDark',        name: 'CAT Dark',       group: 'CAT',      texture: 'cat',        depth: 'low',    vars: { primary: '#1c3324', secondary: '#0a130d', edge: '#05100a', glow: 'rgba(70,224,138,0.35)', eyeBg: '#000', pupil: '#8fd9ab' } },
    { id: 'catGreen',       name: 'CAT Green',      group: 'CAT',      texture: 'cat',        depth: 'low',    vars: { primary: '#7be08a', secondary: '#2f9e4f', edge: '#175c2a', glow: 'rgba(123,224,138,0.5)', eyeBg: '#0a2211', pupil: '#eafff0' } },
    { id: 'catPurple',      name: 'CAT Purple',     group: 'CAT',      texture: 'cat',        depth: 'low',    vars: { primary: '#b98bff', secondary: '#6a3fc2', edge: '#3c2270', glow: 'rgba(185,139,255,0.5)', eyeBg: '#190f33', pupil: '#f1e9ff' } },
    { id: 'minecraft',      name: 'Minecraft',      group: 'Minecraft',texture: 'pixel',      depth: 'off',    vars: { primary: '#5fa63a', secondary: '#3d7524', edge: '#1a140c', glow: 'rgba(95,166,58,0.35)', eyeBg: '#1a140c', pupil: '#f0e6d2' } },
    { id: 'minecraftGrass', name: 'Minecraft Grass',group: 'Minecraft',texture: 'pixel',      depth: 'off',    vars: { primary: '#6fbf4a', secondary: '#4a8a2c', edge: '#3a2a14', glow: 'rgba(111,191,74,0.35)', eyeBg: '#241a0c', pupil: '#f0e6d2' } },
    { id: 'minecraftStone', name: 'Minecraft Stone',group: 'Minecraft',texture: 'pixel',      depth: 'off',    vars: { primary: '#8a8a86', secondary: '#5c5c58', edge: '#2e2e2c', glow: 'rgba(138,138,134,0.3)', eyeBg: '#1c1c1a', pupil: '#eee' } },
    { id: 'minecraftDiamond',name:'Minecraft Diamond',group:'Minecraft',texture: 'pixel',     depth: 'off',    vars: { primary: '#5ee3e0', secondary: '#2ba6a3', edge: '#143f3e', glow: 'rgba(94,227,224,0.45)', eyeBg: '#062120', pupil: '#eafffe' } },
    { id: 'minecraftEmerald',name:'Minecraft Emerald',group:'Minecraft',texture:'pixel',      depth: 'off',    vars: { primary: '#3fd67a', secondary: '#1f9c50', edge: '#0e4a26', glow: 'rgba(63,214,122,0.4)', eyeBg: '#052014', pupil: '#eafff2' } },
    { id: 'minecraftObsidian',name:'Minecraft Obsidian',group:'Minecraft',texture:'pixel',    depth: 'off',    vars: { primary: '#2b1f47', secondary: '#150f26', edge: '#0a0715', glow: 'rgba(123,63,255,0.35)', eyeBg: '#000', pupil: '#c9b3ff' } },
    { id: 'gameArcade',     name: 'Game Arcade',    group: 'Game',     texture: 'arcade',     depth: 'medium', vars: { primary: '#ff3d7f', secondary: '#7d1fff', edge: '#2a0d4a', glow: 'rgba(255,61,127,0.55)', eyeBg: '#150522', pupil: '#fff' } },
    { id: 'gamePixel',      name: 'Game Pixel',     group: 'Game',     texture: 'pixel',      depth: 'off',    vars: { primary: '#ffcc00', secondary: '#ff5e5e', edge: '#4a1a1a', glow: 'rgba(255,204,0,0.4)', eyeBg: '#2a0a0a', pupil: '#fff' } },
    { id: 'gameRetro',      name: 'Game Retro',     group: 'Game',     texture: 'retro',      depth: 'low',    vars: { primary: '#ff8a3d', secondary: '#c94f1e', edge: '#4a220c', glow: 'rgba(255,138,61,0.45)', eyeBg: '#2a1206', pupil: '#ffe9d4' } },
    { id: 'neu',            name: 'Neumorphism',    group: 'Surface',  texture: 'neu',        depth: 'low',    vars: { primary: '#e0e5ec', secondary: '#e0e5ec', edge: '#c8ccd3', glow: 'rgba(0,0,0,0.08)', eyeBg: '#4a4f57', pupil: '#eef1f5' } },
    { id: 'skeu',            name: 'Skeuomorphism', group: 'Surface',  texture: 'skeu',       depth: 'high',   vars: { primary: '#d8c9a3', secondary: '#a8895a', edge: '#5c4526', glow: 'rgba(0,0,0,0.35)', eyeBg: '#2c2013', pupil: '#fff4dd' } },
    { id: 'glass',           name: 'Glassmorphism', group: 'Surface',  texture: 'glass',      depth: 'medium', vars: { primary: 'rgba(255,255,255,0.16)', secondary: 'rgba(255,255,255,0.04)', edge: 'rgba(255,255,255,0.35)', glow: 'rgba(180,210,255,0.4)', eyeBg: 'rgba(10,10,15,0.5)', pupil: '#eaf3ff' } },
    { id: 'crystal',         name: 'Crystal',       group: 'Surface',  texture: 'crystal',    depth: 'high',   vars: { primary: '#bcd8ff', secondary: '#6fa3e0', edge: '#dff0ff', glow: 'rgba(188,216,255,0.6)', eyeBg: '#0d2340', pupil: '#eaf6ff' } },
    { id: 'holo',            name: 'Holographic',   group: 'Surface',  texture: 'holo',       depth: 'medium', vars: { primary: '#ff9de2', secondary: '#9dfff0', edge: '#ffffff', glow: 'rgba(157,255,240,0.5)', eyeBg: '#1a0a24', pupil: '#fff' } },
    { id: 'cyber',           name: 'Cyber',         group: 'Tech',     texture: 'cyber',      depth: 'medium', vars: { primary: '#0a0e14', secondary: '#001a12', edge: '#00ffb2', glow: 'rgba(0,255,178,0.6)', eyeBg: '#001a12', pupil: '#00ffb2' } },
    { id: 'quantum',         name: 'Quantum',       group: 'Tech',     texture: 'quantum',    depth: 'medium', vars: { primary: '#1a0a2e', secondary: '#0a0518', edge: '#7b3fff', glow: 'rgba(123,63,255,0.6)', eyeBg: '#0a0518', pupil: '#c9b3ff' } },
    { id: 'scientific',      name: 'Scientific',    group: 'Tech',     texture: 'scientific', depth: 'low',    vars: { primary: '#eef3f8', secondary: '#d7e3ee', edge: '#3a6ea5', glow: 'rgba(58,110,165,0.3)', eyeBg: '#12324d', pupil: '#eef3f8' } },
    { id: 'crt',             name: 'CRT Terminal',  group: 'Tech',     texture: 'crt',        depth: 'low',    vars: { primary: '#061a08', secondary: '#020f04', edge: '#1c4a20', glow: 'rgba(60,255,90,0.5)', eyeBg: '#020f04', pupil: '#3cff5a' } },
    { id: 'custom',          name: 'Custom',        group: 'Custom',   texture: 'flat',       depth: 'low',    vars: { primary: '#46e08a', secondary: '#1f7d47', edge: '#163d26', glow: 'rgba(70,224,138,0.5)', eyeBg: '#04140b', pupil: '#d9ffe4' } }
  ];
  var THEME_MAP = {};
  BOT_THEMES.forEach(function (t) { THEME_MAP[t.id] = t; });

  var FACES = ['round', 'square', 'blob', 'pixel'];
  var EYES = ['dot', 'oval', 'wide', 'sleepy'];
  var DEPTHS = ['off', 'low', 'medium', 'high'];
  var POSITIONS = ['br', 'bl', 'tr', 'tl'];
  var SIZES = ['sm', 'md', 'lg', 'xl'];
  var SHADES = ['light', 'normal', 'dark'];
  var SLEEP_OPTIONS = { '30s': 30000, '1m': 60000, '5m': 300000, '10m': 600000, 'off': 0 };

  var DEFAULTS = {
    visible: true,
    theme: 'classic',
    shade: 'normal',
    customColors: null,        // { primary, secondary, highlight, shadow } overrides, only when theme === 'custom' or user overrode
    face: 'round',
    eyes: 'dot',
    depth: null,               // null = use theme default
    glow: true,
    size: 'md',
    position: 'br',
    opacity: 1,
    animSpeed: 'normal',       // slow | normal | fast
    animIntensity: 'normal',   // subtle | normal | strong
    animate: true,
    interactive: true,
    sleepAfter: '1m',
    expression: null           // manual override; null = engine-driven
  };

  /* ------------------------------------------------------------------
     Storage
     ------------------------------------------------------------------ */
  function assign(t, s) { for (var k in s) if (Object.prototype.hasOwnProperty.call(s, k)) t[k] = s[k]; return t; }

  function migrateLegacy(s) {
    // one-time pickup from the old separate stores, best-effort only
    try {
      var oldBot = JSON.parse(localStorage.getItem('fomoji_bot_v1') || 'null');
      if (oldBot && s.visible === undefined) assign(s, { visible: oldBot.visible, animate: oldBot.animate, interactive: oldBot.interactive });
    } catch (e) {}
    return s;
  }

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return migrateLegacy(assign({}, DEFAULTS));
      var parsed = JSON.parse(raw);
      return assign(assign({}, DEFAULTS), parsed && typeof parsed === 'object' ? parsed : {});
    } catch (e) { return assign({}, DEFAULTS); }
  }
  function save(s) {
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* guest / storage unavailable: just won't persist */ }
  }

  function reduceMotion() {
    var html = document.documentElement;
    return html.classList.contains('reduce-motion') ||
      html.dataset.motion === 'reduced' || html.dataset.motion === 'none' ||
      (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  /* ------------------------------------------------------------------
     Emotion presets — 21 named states built from a small set of reusable
     eye/mouth/body primitives (see CSS), not 21 bespoke animations.
     ------------------------------------------------------------------ */
  var EMOTIONS = {
    idle:      { eye: 'normal',  mouth: 'line',   anim: '',          ms: 0 },
    smile:     { eye: 'normal',  mouth: 'smile',  anim: 'pop',       ms: 1200 },
    happy:     { eye: 'happy',   mouth: 'big',    anim: 'bounce',    ms: 1200 },
    sad:       { eye: 'normal',  mouth: 'frown',  anim: 'droop',     ms: 1600 },
    angry:     { eye: 'narrow',  mouth: 'frown',  anim: 'shake',     ms: 900 },
    cry:       { eye: 'squint',  mouth: 'frown',  anim: 'droop',     ms: 1600 },
    sleep:     { eye: 'closed',  mouth: 'line',   anim: 'breathe',   ms: 0 },
    wake:      { eye: 'wide',    mouth: 'smile',  anim: 'pop',       ms: 500 },
    surprised: { eye: 'wide',    mouth: 'open',   anim: 'pop',       ms: 700 },
    confused:  { eye: 'normal',  mouth: 'wavy',   anim: 'tilt',      ms: 1200 },
    thinking:  { eye: 'up',      mouth: 'line',   anim: 'sway',      ms: 0 },
    working:   { eye: 'normal',  mouth: 'line',   anim: 'pulse',     ms: 0 },
    excited:   { eye: 'happy',   mouth: 'big',    anim: 'bouncefast',ms: 1000 },
    blink:     { eye: 'closed',  mouth: 'line',   anim: '',          ms: 160 },
    wave:      { eye: 'normal',  mouth: 'smile',  anim: 'wave',      ms: 600 },
    bounce:    { eye: 'normal',  mouth: 'smile',  anim: 'bounce',    ms: 600 },
    dance:     { eye: 'happy',   mouth: 'smile',  anim: 'dance',     ms: 1400 },
    success:   { eye: 'happy',   mouth: 'big',    anim: 'pop',       ms: 1000 },
    error:     { eye: 'narrow',  mouth: 'frown',  anim: 'shake',     ms: 900 },
    celebrate: { eye: 'happy',   mouth: 'big',    anim: 'bouncefast',ms: 1400 },
    goodbye:   { eye: 'normal',  mouth: 'smile',  anim: 'wave',      ms: 1400 }
  };
  // maps the old FomojiCompanion states + a couple of friendly aliases
  var STATE_ALIAS = { loading: 'working', press: 'bounce', near: 'smile' };

  var current = load();
  var el = null, eyeL = null, eyeR = null, mouthEl = null, zzzEl = null;
  var reactionTimer = null, blinkTimer = null, sleepTimer = null, rafId = null;
  var reactionIndex = 0;
  var TAP_REACTIONS = ['happy', 'wave', 'bounce', 'excited'];
  var longPressTimer = null, lastActivityAt = Date.now();

  /* ------------------------------------------------------------------
     Build (once)
     ------------------------------------------------------------------ */
  function build() {
    el = document.createElement('div');
    el.className = 'fabot';
    el.setAttribute('role', 'button');
    el.setAttribute('tabindex', '0');
    el.setAttribute('aria-label', 'Fomoji companion bot');
    el.innerHTML =
      '<div class="fabot-body">' +
        '<div class="fabot-shine"></div>' +
        '<div class="fabot-eyes">' +
          '<div class="fabot-eye fabot-eye-l"><div class="fabot-pupil"></div></div>' +
          '<div class="fabot-eye fabot-eye-r"><div class="fabot-pupil"></div></div>' +
        '</div>' +
        '<div class="fabot-mouth"></div>' +
        '<div class="fabot-zzz" aria-hidden="true">z z z</div>' +
      '</div>';
    document.body.appendChild(el);
    eyeL = el.querySelector('.fabot-eye-l .fabot-pupil');
    eyeR = el.querySelector('.fabot-eye-r .fabot-pupil');
    mouthEl = el.querySelector('.fabot-mouth');
    zzzEl = el.querySelector('.fabot-zzz');

    document.addEventListener('pointermove', onDocPointerMove, { passive: true });
    el.addEventListener('pointerleave', recenterEyes);
    el.addEventListener('click', function () { onActivate('tap'); });
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onActivate('tap'); }
    });
    el.addEventListener('pointerdown', function (e) {
      markActivity();
      longPressTimer = setTimeout(function () { onActivate('long'); }, 550);
    });
    ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (ev) {
      el.addEventListener(ev, function () { if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; } });
    });
    el.addEventListener('pointerenter', function () { markActivity(); if (current.interactive && current.animate && !isSleeping()) setEmotion('smile'); });

    ['pointermove', 'touchstart', 'keydown', 'click'].forEach(function (ev) {
      document.addEventListener(ev, markActivity, { passive: true });
    });

    document.addEventListener('visibilitychange', function () {
      if (!el) return;
      el.classList.toggle('is-paused', document.hidden);
    });
  }

  function markActivity() {
    lastActivityAt = Date.now();
    if (isSleeping()) wake();
    scheduleSleep();
  }

  /* ------------------------------------------------------------------
     Positioning — clears the tab bar / important chrome, never
     overlaps buttons or auth cards (fixed corner placement + safe-area).
     ------------------------------------------------------------------ */
  function positionForPage() {
    if (!el) return;
    var tabbar = document.querySelector('.tabbar');
    var isTop = document.documentElement.dataset.tabbarPos === 'top';
    var clearance = (tabbar && !isTop) ? 'calc(86px + var(--safe-b, 0px) + 10px)' : 'calc(16px + var(--safe-b, 0px))';
    el.style.setProperty('--fabot-clearance', clearance);
  }

  /* ------------------------------------------------------------------
     Eye tracking (pointer) — cheap: only active within a radius, off
     entirely while asleep/disabled/reduced motion.
     ------------------------------------------------------------------ */
  function onDocPointerMove(e) {
    if (!el || !current.interactive || !current.animate || reduceMotion() || isSleeping()) return;
    var rect = el.getBoundingClientRect();
    var cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
    var dx = e.clientX - cx, dy = e.clientY - cy;
    var dist = Math.sqrt(dx * dx + dy * dy);
    if (dist > 280) { recenterEyes(); return; }
    var maxShift = 2.6;
    setEyeOffset(Math.max(-1, Math.min(1, dx / 140)) * maxShift, Math.max(-1, Math.min(1, dy / 140)) * maxShift);
  }
  function setEyeOffset(x, y) {
    if (!eyeL || !eyeR) return;
    var t = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px)';
    eyeL.style.transform = t; eyeR.style.transform = t;
  }
  function recenterEyes() { setEyeOffset(0, 0); }

  /* ------------------------------------------------------------------
     Interaction -> emotion
     ------------------------------------------------------------------ */
  function onActivate(kind) {
    if (!current.interactive || !el) return;
    markActivity();
    var name;
    if (kind === 'long') {
      name = 'thinking';
    } else {
      name = TAP_REACTIONS[reactionIndex % TAP_REACTIONS.length];
      reactionIndex++;
    }
    setEmotion(name);
  }

  /* ------------------------------------------------------------------
     Sleep system
     ------------------------------------------------------------------ */
  function isSleeping() { return el && el.classList.contains('is-asleep'); }
  function scheduleSleep() {
    if (sleepTimer) clearTimeout(sleepTimer);
    var ms = SLEEP_OPTIONS[current.sleepAfter];
    if (!ms) return; // 'off'
    sleepTimer = setTimeout(function () {
      if (Date.now() - lastActivityAt >= ms - 50) sleep();
    }, ms);
  }
  function sleep() {
    if (!el || isSleeping()) return;
    el.classList.add('is-asleep');
    setEmotion('sleep', true);
  }
  function wake() {
    if (!el || !isSleeping()) return;
    el.classList.remove('is-asleep');
    setEmotion('wake');
  }

  /* ------------------------------------------------------------------
     Emotion application
     ------------------------------------------------------------------ */
  var ANIM_CLASSES = ['pop', 'bounce', 'bouncefast', 'shake', 'droop', 'tilt', 'sway', 'pulse', 'wave', 'dance', 'breathe'];

  function setEmotion(name, persist) {
    if (!el) return;
    name = STATE_ALIAS[name] || name;
    var def = EMOTIONS[name] || EMOTIONS.idle;
    if (reactionTimer) { clearTimeout(reactionTimer); reactionTimer = null; }
    el.dataset.eyeState = def.eye;
    el.dataset.mouthState = def.mouth;
    ANIM_CLASSES.forEach(function (c) { el.classList.remove('do-' + c); });
    if (!reduceMotion() && current.animate && def.anim) el.classList.add('do-' + def.anim);
    el.dataset.emotion = name;
    if (def.ms && !persist && !current.expression) {
      reactionTimer = setTimeout(function () {
        if (!isSleeping()) applyBaseEmotion();
      }, def.ms);
    }
  }
  function applyBaseEmotion() {
    setEmotion(current.expression || (isSleeping() ? 'sleep' : 'idle'), true);
  }

  /* ------------------------------------------------------------------
     Blinking — small, independent, self-scheduling loop.
     ------------------------------------------------------------------ */
  function scheduleBlink() {
    clearTimeout(blinkTimer);
    blinkTimer = setTimeout(function () {
      if (el && current.animate && !reduceMotion() && !isSleeping() && !current.expression && el.dataset.emotion === 'idle') {
        el.dataset.eyeState = 'closed';
        setTimeout(function () { if (el && el.dataset.emotion === 'idle') el.dataset.eyeState = 'normal'; }, 150);
      }
      scheduleBlink();
    }, 2600 + Math.random() * 3000);
  }

  /* ------------------------------------------------------------------
     Apply full visual state from `current`
     ------------------------------------------------------------------ */
  function applyTheme() {
    if (!el) return;
    var theme = THEME_MAP[current.theme] || THEME_MAP[DEFAULTS.theme];
    el.dataset.faBotTheme = theme.id;
    el.dataset.texture = theme.texture;
    var vars = assign({}, theme.vars);
    if (current.customColors) assign(vars, current.customColors);
    el.style.setProperty('--bot-primary', vars.primary);
    el.style.setProperty('--bot-secondary', vars.secondary);
    el.style.setProperty('--bot-edge', vars.highlight || vars.edge);
    el.style.setProperty('--bot-shadow-c', vars.shadow || 'rgba(0,0,0,0.45)');
    el.style.setProperty('--bot-glow', current.glow ? vars.glow : 'transparent');
    el.style.setProperty('--bot-eye-bg', vars.eyeBg);
    el.style.setProperty('--bot-pupil', vars.pupil);
    el.dataset.depth = current.depth || theme.depth || 'low';
  }

  var SHADE_FILTER = { light: 'brightness(1.18) saturate(0.95)', normal: 'none', dark: 'brightness(0.78)' };
  var SIZE_SCALE = { sm: 0.78, md: 1, lg: 1.28, xl: 1.6 };
  var SPEED_MS = { slow: '4.6s', normal: '3.2s', fast: '2s' };
  var INTENSITY_AMP = { subtle: '2px', normal: '5px', strong: '9px' };

  function applyState() {
    if (!el) return;
    el.classList.toggle('is-hidden', !current.visible);
    el.classList.toggle('no-motion', !current.animate || reduceMotion());
    el.classList.toggle('no-interact', !current.interactive);
    el.setAttribute('aria-hidden', current.visible ? 'false' : 'true');
    el.dataset.face = current.face;
    el.dataset.eyes = current.eyes;
    el.dataset.size = current.size;
    el.dataset.position = current.position;
    el.style.setProperty('--bot-scale', SIZE_SCALE[current.size] || 1);
    el.style.setProperty('--bot-opacity', current.opacity != null ? current.opacity : 1);
    el.style.setProperty('--bot-shade-filter', SHADE_FILTER[current.shade] || 'none');
    el.style.setProperty('--bot-float-dur', SPEED_MS[current.animSpeed] || '3.2s');
    el.style.setProperty('--bot-float-amp', INTENSITY_AMP[current.animIntensity] || '5px');
    applyTheme();
    positionForPage();
    if (current.expression) {
      setEmotion(current.expression, true);
    } else if (!isSleeping()) {
      applyBaseEmotion();
    }
    if (!current.sleepAfter || current.sleepAfter === 'off') {
      if (sleepTimer) clearTimeout(sleepTimer);
      if (isSleeping()) wake();
    } else {
      scheduleSleep();
    }
  }

  function mount() {
    if (el) { applyState(); return; }
    build();
    applyState();
    scheduleBlink();
  }

  function emit() {
    document.dispatchEvent(new CustomEvent('fomoji-animated-bot-change', { detail: assign({}, current) }));
  }

  window.addEventListener('resize', function () { if (el) positionForPage(); });
  document.addEventListener('fomoji-tabbar-change', function () { if (el) positionForPage(); });

  /* ------------------------------------------------------------------
     Public API
     ------------------------------------------------------------------ */
  window.AnimatedBot = {
    THEMES: BOT_THEMES,
    FACES: FACES,
    EYES: EYES,
    DEPTHS: DEPTHS,
    POSITIONS: POSITIONS,
    SIZES: SIZES,
    SHADES: SHADES,
    EMOTIONS: Object.keys(EMOTIONS),
    SLEEP_OPTIONS: Object.keys(SLEEP_OPTIONS),
    defaults: DEFAULTS,
    get: function () { return assign({}, current); },
    set: function (partial) {
      current = assign(assign({}, current), partial || {});
      save(current);
      if (!el) build();
      applyState();
      emit();
    },
    reset: function () {
      current = assign({}, DEFAULTS);
      save(current);
      if (!el) build();
      applyState();
      emit();
    },
    /** Non-blocking reaction hook for the rest of the app (e.g. an
     * optional GOODBYE on the sign-out screen). Never throws, never
     * required by any caller. */
    react: function (state) {
      try {
        if (!el || !current.visible || !current.interactive) return;
        markActivity();
        setEmotion(state);
      } catch (e) { /* decorative only */ }
    },
    mountPreview: function (container, overrideSettings) {
      if (!container) return;
      var s = assign(assign({}, current), overrideSettings || {});
      var theme = THEME_MAP[s.theme] || THEME_MAP.classic;
      var vars = assign({}, theme.vars);
      if (s.customColors) assign(vars, s.customColors);
      container.innerHTML =
        '<div class="fabot fabot-preview" data-fa-bot-theme="' + theme.id + '" data-texture="' + theme.texture + '" ' +
        'data-depth="' + (s.depth || theme.depth) + '" data-face="' + s.face + '" data-eyes="' + s.eyes + '" ' +
        'data-eye-state="normal" data-mouth-state="smile" data-emotion="smile" data-size="md" style="' +
        '--bot-primary:' + vars.primary + ';--bot-secondary:' + vars.secondary + ';--bot-edge:' + (vars.highlight || vars.edge) + ';' +
        '--bot-glow:' + (s.glow ? vars.glow : 'transparent') + ';--bot-eye-bg:' + vars.eyeBg + ';--bot-pupil:' + vars.pupil + ';' +
        '--bot-scale:1.6;--bot-opacity:' + (s.opacity != null ? s.opacity : 1) + ';--bot-shade-filter:' + (SHADE_FILTER[s.shade] || 'none') + ';">' +
        '<div class="fabot-body"><div class="fabot-shine"></div><div class="fabot-eyes">' +
        '<div class="fabot-eye fabot-eye-l"><div class="fabot-pupil"></div></div>' +
        '<div class="fabot-eye fabot-eye-r"><div class="fabot-pupil"></div></div></div>' +
        '<div class="fabot-mouth"></div></div></div>';
    }
  };

  // Back-compat shim: index.html / signup.html already call
  // window.FomojiCompanion?.react('loading' | 'success' | 'error') at
  // their real auth loading/success/error points. Keep that contract
  // working without editing those files.
  window.FomojiCompanion = {
    react: function (state) { window.AnimatedBot.react(state); },
    mountPreview: function (container) { window.AnimatedBot.mountPreview(container); }
  };

  function boot() {
    try { mount(); } catch (e) { /* bot is decorative only — never let it break the page */ }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
