/* ==========================================================================
   FOMOJI — Gesture Studio
   Frontend-only. Every gesture points at the same safe action registry
   fomoji-tabbar.js already exposes (FomojiTabbar.runAction) — nothing here
   can execute arbitrary code, only a fixed, named action.

   Honesty note: this implements a deliberately restrained set of gestures —
   ones that can be recognized reliably without hijacking ordinary taps
   anywhere on the page (a single global "tap" gesture would break every
   button). Multi-finger and diagonal gestures are best-effort and may not
   register on every browser/trackpad; nothing here is presented as
   guaranteed-universal.

   Master on/off reuses the existing FomojiAppearance "gestures" flag from
   the Appearance panel, so there's one on/off switch, not two competing
   ones. This module adds per-gesture mapping, a "reduced gestures" preset,
   and conflict detection on top of that.

   Exposes window.FomojiGestures:
     SLOTS                 -> [{ id, label, group, scope }]
     ACTIONS                -> safe action list a slot can be bound to (includes
                                'tabNext' / 'tabPrev', special-cased for swipes)
     getBindings()           -> { slotId: actionId|null, ... }
     setBinding(slotId, actionId|null)
     findConflicts()         -> { actionId: [slotId, ...] } for actions bound to 2+ slots
     isMasterEnabled()        -> reads FomojiAppearance.gestures
     setMasterEnabled(bool)
     isReduced() / setReduced(bool)  -> keeps only swipeLeft/swipeRight/longPressTabbar
     resetToDefault()
   ========================================================================== */
(function () {
  'use strict';

  var KEY = 'fomoji_gestures_v1';

  var SLOTS = [
    { id: 'swipeLeft',          label: 'Swipe left',            group: 'Swipe (1 finger)', reducedSafe: true },
    { id: 'swipeRight',         label: 'Swipe right',           group: 'Swipe (1 finger)', reducedSafe: true },
    { id: 'swipeUp',            label: 'Swipe up',              group: 'Swipe (1 finger)' },
    { id: 'swipeDown',          label: 'Swipe down',            group: 'Swipe (1 finger)' },
    { id: 'twoFingerTap',       label: 'Two-finger tap',        group: 'Multi-finger' },
    { id: 'twoFingerSwipeLeft', label: 'Two-finger swipe left', group: 'Multi-finger' },
    { id: 'twoFingerSwipeRight',label: 'Two-finger swipe right',group: 'Multi-finger' },
    { id: 'twoFingerSwipeUp',   label: 'Two-finger swipe up',   group: 'Multi-finger' },
    { id: 'twoFingerSwipeDown', label: 'Two-finger swipe down', group: 'Multi-finger' },
    { id: 'longPressTabbar',    label: 'Long-press the tab bar',group: 'Press & tap', reducedSafe: true },
    { id: 'doubleTapLogo',      label: 'Double-tap the logo',   group: 'Press & tap' },
    { id: 'tripleTapLogo',      label: 'Triple-tap the logo',   group: 'Press & tap' }
  ];
  var SLOT_MAP = {};
  SLOTS.forEach(function (s) { SLOT_MAP[s.id] = s; });

  var SPECIAL_ACTIONS = [
    { id: 'tabNext', label: 'Next tab', group: 'Tab bar' },
    { id: 'tabPrev', label: 'Previous tab', group: 'Tab bar' }
  ];

  function actionRegistry() {
    var base = (window.FomojiTabbar && FomojiTabbar.ACTIONS) || [];
    return SPECIAL_ACTIONS.concat(base);
  }

  var DEFAULT_BINDINGS = {
    swipeLeft: 'tabNext',
    swipeRight: 'tabPrev',
    swipeUp: null, swipeDown: null,
    twoFingerTap: null,
    twoFingerSwipeLeft: null, twoFingerSwipeRight: null,
    twoFingerSwipeUp: null, twoFingerSwipeDown: null,
    longPressTabbar: null,
    doubleTapLogo: null, tripleTapLogo: null
  };
  var DEFAULT_STATE = { bindings: DEFAULT_BINDINGS, reduced: false };

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return clone(DEFAULT_STATE);
      var parsed = JSON.parse(raw);
      var bindings = Object.assign({}, DEFAULT_BINDINGS, parsed.bindings || {});
      return { bindings: bindings, reduced: !!parsed.reduced };
    } catch (e) { return clone(DEFAULT_STATE); }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }
  function emit() {
    document.dispatchEvent(new CustomEvent('fomoji-gestures-change', { detail: clone(state) }));
  }

  var state = load();

  function isMasterEnabled() {
    return !window.FomojiAppearance || FomojiAppearance.get().gestures !== false;
  }
  function setMasterEnabled(on) {
    if (window.FomojiAppearance) FomojiAppearance.set({ gestures: !!on });
  }

  function activeBinding(slotId) {
    var slot = SLOT_MAP[slotId];
    if (state.reduced && slot && !slot.reducedSafe) return null;
    return state.bindings[slotId] || null;
  }

  function findConflicts() {
    var byAction = {};
    Object.keys(state.bindings).forEach(function (slotId) {
      var a = state.bindings[slotId];
      if (!a) return;
      (byAction[a] = byAction[a] || []).push(slotId);
    });
    var out = {};
    Object.keys(byAction).forEach(function (a) { if (byAction[a].length > 1) out[a] = byAction[a]; });
    return out;
  }

  function runSlot(slotId) {
    if (!isMasterEnabled()) return;
    var actionId = activeBinding(slotId);
    if (!actionId) return;
    if (actionId === 'tabNext' || actionId === 'tabPrev') { navTab(actionId === 'tabNext' ? 1 : -1); return; }
    if (window.FomojiTabbar) FomojiTabbar.runAction(actionId);
  }

  function navTab(delta) {
    var tabs = Array.prototype.slice.call(document.querySelectorAll('nav.tabbar .tab[href]'));
    if (tabs.length < 2) return;
    var idx = tabs.findIndex(function (a) { return a.classList.contains('is-active'); });
    if (idx === -1) return;
    var next = idx + delta;
    if (next < 0 || next >= tabs.length) return;
    window.location.href = tabs[next].getAttribute('href');
  }

  /* ---- direction detection (single + two finger) ---- */
  function directionOf(dx, dy) {
    if (Math.abs(dx) < 60 && Math.abs(dy) < 60) return null;
    return Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? 'Left' : 'Right') : (dy < 0 ? 'Up' : 'Down');
  }

  function initSwipe() {
    var startX = 0, startY = 0, startFingers = 0, tracking = false;
    document.addEventListener('touchstart', function (e) {
      if (!isMasterEnabled()) return;
      startFingers = e.touches.length;
      var t = e.touches[0];
      startX = t.clientX; startY = t.clientY; tracking = true;
    }, { passive: true });
    document.addEventListener('touchend', function (e) {
      if (!tracking || !isMasterEnabled()) { tracking = false; return; }
      tracking = false;
      var t = e.changedTouches[0];
      var dir = directionOf(t.clientX - startX, t.clientY - startY);
      if (!dir) return;
      var prefix = startFingers >= 2 ? 'twoFingerSwipe' : 'swipe';
      runSlot(prefix + dir);
    }, { passive: true });
  }

  function initTwoFingerTap() {
    document.addEventListener('touchstart', function (e) {
      if (!isMasterEnabled() || e.touches.length !== 2) return;
      var fired = false;
      var onEnd = function () {
        if (!fired) { fired = true; runSlot('twoFingerTap'); }
        document.removeEventListener('touchend', onEnd);
      };
      document.addEventListener('touchend', onEnd, { once: true });
    }, { passive: true });
  }

  function initLongPressTabbar() {
    var nav = document.querySelector('nav.tabbar');
    if (!nav) return;
    var timer = null;
    var start = function () {
      if (!isMasterEnabled()) return;
      timer = window.setTimeout(function () { runSlot('longPressTabbar'); }, 600);
    };
    var cancel = function () { if (timer) { window.clearTimeout(timer); timer = null; } };
    nav.addEventListener('touchstart', start, { passive: true });
    nav.addEventListener('touchend', cancel, { passive: true });
    nav.addEventListener('touchmove', cancel, { passive: true });
    nav.addEventListener('mousedown', start);
    nav.addEventListener('mouseup', cancel);
    nav.addEventListener('mouseleave', cancel);
  }

  function initLogoTaps() {
    var logo = document.querySelector('.topbar img');
    if (!logo) return;
    var target = logo.closest('a') || logo;
    var count = 0, timer = null;
    target.addEventListener('click', function (e) {
      if (!isMasterEnabled()) return; // let the default link behave normally
      var isLink = target.tagName === 'A';
      count++;
      if (count === 1 && isLink) {
        // don't block a plain single tap from going home immediately unless
        // a double/triple binding exists — otherwise there'd be a needless delay
        if (!activeBinding('doubleTapLogo') && !activeBinding('tripleTapLogo')) { count = 0; return; }
      }
      e.preventDefault();
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        if (count === 2) runSlot('doubleTapLogo');
        else if (count >= 3) runSlot('tripleTapLogo');
        else if (isLink) window.location.href = target.getAttribute('href');
        count = 0;
      }, 320);
    });
  }

  window.FomojiGestures = {
    SLOTS: SLOTS,
    ACTIONS: actionRegistry(),
    getBindings: function () { return Object.assign({}, state.bindings); },
    setBinding: function (slotId, actionId) {
      if (!SLOT_MAP[slotId]) return false;
      state.bindings[slotId] = actionId || null;
      save(); emit();
      return true;
    },
    findConflicts: findConflicts,
    isMasterEnabled: isMasterEnabled,
    setMasterEnabled: setMasterEnabled,
    isReduced: function () { return !!state.reduced; },
    setReduced: function (on) { state.reduced = !!on; save(); emit(); },
    resetToDefault: function () { state = clone(DEFAULT_STATE); save(); emit(); }
  };

  function boot() {
    initSwipe();
    initTwoFingerTap();
    initLongPressTabbar();
    initLogoTaps();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
