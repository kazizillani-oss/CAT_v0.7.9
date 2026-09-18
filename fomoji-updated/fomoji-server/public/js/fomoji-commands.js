/* ==========================================================================
   FOMOJI — command palette + customizable keyboard shortcuts
   Frontend-only, same honesty rule as fomoji-auth.js: nothing here talks to
   a server. Shortcuts persist to localStorage per-browser. Include on every
   page (already wired in <head>, right after fomoji-fx.js).

   Exposes window.FomojiCommands:
     list                      -> all commands (id, label, group, shortcutId?)
     getShortcuts()            -> { shortcutId: 'mod+k', ... }  (resolved, with defaults filled in)
     setShortcut(id, combo)    -> save a remapped combo (combo can be null to clear)
     resetShortcuts()          -> restore every default
     findConflicts()           -> { combo: [shortcutId, ...] } for any combo used twice+
     comboLabel(combo)         -> platform-appropriate display string, e.g. "⌘K" / "Ctrl+K"
     open() / close()          -> control the palette overlay directly
   ========================================================================== */
(function () {
  'use strict';

  var SHORTCUT_KEY = 'fomoji_shortcuts_v1';
  var isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent || '');

  // Every shortcut-able action gets a stable id here, independent of the
  // command's label (so relabeling a command never orphans a saved combo).
  var DEFAULT_SHORTCUTS = {
    palette:  'mod+k',
    home:     'mod+h',
    settings: 'mod+,',
    about:    'mod+i',
    help:     'mod+/',
    signout:  'mod+shift+q'
  };

  function go(path) {
    var hashIdx = path.indexOf('#');
    var target = hashIdx >= 0 ? path.slice(0, hashIdx) : path;
    var hash = hashIdx >= 0 ? path.slice(hashIdx) : '';
    var here = location.pathname.split('/').pop() || 'index.html';
    if (target === here) {
      if (hash) { location.hash = hash; } else { window.scrollTo(0, 0); }
    } else {
      location.href = path;
    }
  }

  var COMMANDS = [
    { id: 'openHome',       label: 'Open Home',           group: 'Navigate',    shortcutId: 'home',     run: function () { go('home.html'); } },
    { id: 'openAbout',      label: 'Open About',          group: 'Navigate',    shortcutId: 'about',    run: function () { go('about.html'); } },
    { id: 'openSettings',   label: 'Open Settings',       group: 'Navigate',    shortcutId: 'settings', run: function () { go('settings.html'); } },
    { id: 'openHelp',       label: 'Open Help',           group: 'Navigate',    shortcutId: 'help',     run: function () { go('help.html'); } },
    { id: 'openAppearance', label: 'Theme Studio',        group: 'Personalize', run: function () { go('settings.html#appearance'); } },
    { id: 'openShortcuts',  label: 'Keyboard shortcuts',  group: 'Personalize', run: function () { go('settings.html#shortcuts'); } },
    { id: 'openSecurity',   label: 'Security',            group: 'Account',     run: function () { go('settings.html#security'); } },
    { id: 'openConnected',  label: 'Connected apps',      group: 'Account',     run: function () { go('settings.html#connected'); } },
    { id: 'openPrivacy',    label: 'Privacy',             group: 'Account',     run: function () { go('settings.html#privacy'); } },
    { id: 'signOut',        label: 'Sign out',            group: 'Account',     shortcutId: 'signout',  run: function () {
        if (window.FomojiSignOut && typeof FomojiSignOut.trigger === 'function') {
          FomojiSignOut.trigger(function () { go('welcome.html'); });
        } else {
          if (window.FomojiAPI && typeof FomojiAPI.logout === 'function') { try { FomojiAPI.logout(); } catch (e) {} }
          go('welcome.html');
        }
      } }
  ];

  function loadShortcuts() {
    var stored = {};
    try {
      var raw = localStorage.getItem(SHORTCUT_KEY);
      if (raw) stored = JSON.parse(raw) || {};
    } catch (e) { stored = {}; }
    var merged = {};
    for (var k in DEFAULT_SHORTCUTS) merged[k] = DEFAULT_SHORTCUTS[k];
    for (var k2 in stored) merged[k2] = stored[k2]; // null = explicitly unbound
    return merged;
  }

  function saveShortcuts(map) {
    try { localStorage.setItem(SHORTCUT_KEY, JSON.stringify(map)); } catch (e) {}
  }

  var shortcuts = loadShortcuts();

  function findConflicts() {
    var byCombo = {};
    for (var id in shortcuts) {
      var combo = shortcuts[id];
      if (!combo) continue;
      (byCombo[combo] = byCombo[combo] || []).push(id);
    }
    var conflicts = {};
    for (var combo2 in byCombo) if (byCombo[combo2].length > 1) conflicts[combo2] = byCombo[combo2];
    return conflicts;
  }

  function comboLabel(combo) {
    if (!combo) return '—';
    var parts = combo.split('+');
    var out = parts.map(function (p) {
      if (p === 'mod') return isMac ? '\u2318' : 'Ctrl';
      if (p === 'shift') return isMac ? '\u21e7' : 'Shift';
      if (p === 'alt') return isMac ? '\u2325' : 'Alt';
      if (p === 'space') return 'Space';
      if (p === 'arrowup') return '\u2191';
      if (p === 'arrowdown') return '\u2193';
      if (p === 'arrowleft') return '\u2190';
      if (p === 'arrowright') return '\u2192';
      if (p.length === 1) return p.toUpperCase();
      return p.charAt(0).toUpperCase() + p.slice(1);
    });
    return out.join(isMac ? '' : '+');
  }

  function normalizeCombo(e) {
    var key = e.key;
    if (['Control', 'Meta', 'Alt', 'Shift'].indexOf(key) !== -1) return null;
    var parts = [];
    if (e.ctrlKey || e.metaKey) parts.push('mod');
    if (e.altKey) parts.push('alt');
    if (e.shiftKey) parts.push('shift');
    if (key === ' ') key = 'space';
    key = key.toLowerCase();
    parts.push(key);
    return parts.join('+');
  }

  function isTypingTarget(el) {
    if (!el) return false;
    var tag = el.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
  }

  /* ---- palette overlay (built lazily) ---- */
  var overlay = null, listEl = null, inputEl = null, activeIndex = 0, visibleCommands = [];

  function buildOverlay() {
    overlay = document.createElement('div');
    overlay.className = 'cmdk-overlay';
    overlay.innerHTML =
      '<div class="cmdk-panel" role="dialog" aria-label="Command palette">' +
        '<input type="text" class="cmdk-input" placeholder="Search commands\u2026" autocomplete="off" spellcheck="false">' +
        '<div class="cmdk-list" role="listbox"></div>' +
      '</div>';
    document.body.appendChild(overlay);
    inputEl = overlay.querySelector('.cmdk-input');
    listEl = overlay.querySelector('.cmdk-list');

    overlay.addEventListener('mousedown', function (e) { if (e.target === overlay) close(); });
    inputEl.addEventListener('input', function () { render(inputEl.value); });
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); runActive(); }
    });
  }

  function move(delta) {
    if (!visibleCommands.length) return;
    activeIndex = (activeIndex + delta + visibleCommands.length) % visibleCommands.length;
    highlight();
  }

  function highlight() {
    var items = listEl.querySelectorAll('.cmdk-item');
    items.forEach(function (el, i) { el.classList.toggle('is-active', i === activeIndex); });
    var el = items[activeIndex];
    if (el) el.scrollIntoView({ block: 'nearest' });
  }

  function runActive() {
    var cmd = visibleCommands[activeIndex];
    if (cmd) { close(); cmd.run(); }
  }

  function render(query) {
    query = (query || '').trim().toLowerCase();
    visibleCommands = COMMANDS.filter(function (c) { return !query || c.label.toLowerCase().indexOf(query) !== -1; });
    activeIndex = 0;
    if (!visibleCommands.length) {
      listEl.innerHTML = '<div class="cmdk-empty">No matching commands</div>';
      return;
    }
    var groups = [];
    visibleCommands.forEach(function (c) {
      var group = groups[groups.length - 1];
      if (!group || group.name !== c.group) { group = { name: c.group, items: [] }; groups.push(group); }
      group.items.push(c);
    });
    var html = '';
    groups.forEach(function (g) {
      html += '<div class="cmdk-group-label">' + g.name + '</div>';
      g.items.forEach(function (c) {
        var idx = visibleCommands.indexOf(c);
        var combo = c.shortcutId ? shortcuts[c.shortcutId] : null;
        html += '<div class="cmdk-item" data-idx="' + idx + '" role="option">' +
                  '<span>' + c.label + '</span>' +
                  (combo ? '<span class="cmdk-kbd">' + comboLabel(combo) + '</span>' : '') +
                '</div>';
      });
    });
    listEl.innerHTML = html;
    listEl.querySelectorAll('.cmdk-item').forEach(function (el) {
      el.addEventListener('mouseenter', function () { activeIndex = parseInt(el.dataset.idx, 10); highlight(); });
      el.addEventListener('click', function () { activeIndex = parseInt(el.dataset.idx, 10); runActive(); });
    });
    highlight();
  }

  function open() {
    if (!overlay) buildOverlay();
    overlay.classList.add('is-open');
    inputEl.value = '';
    render('');
    window.setTimeout(function () { inputEl.focus(); }, 0);
  }

  function close() {
    if (overlay) overlay.classList.remove('is-open');
  }

  /* ---- global key listener ---- */
  document.addEventListener('keydown', function (e) {
    if (overlay && overlay.classList.contains('is-open')) return; // palette's own listener handles this
    var combo = normalizeCombo(e);
    if (!combo) return;
    if (isTypingTarget(e.target) && combo !== shortcuts.palette) return;

    if (combo === shortcuts.palette) { e.preventDefault(); open(); return; }

    for (var id in shortcuts) {
      if (shortcuts[id] === combo) {
        var cmd = COMMANDS.filter(function (c) { return c.shortcutId === id; })[0];
        if (cmd) { e.preventDefault(); cmd.run(); return; }
      }
    }
  });

  window.FomojiCommands = {
    list: COMMANDS,
    getShortcuts: function () { return Object.assign({}, shortcuts); },
    setShortcut: function (id, combo) {
      shortcuts[id] = combo || null;
      saveShortcuts(shortcuts);
      return findConflicts();
    },
    resetShortcuts: function () {
      shortcuts = Object.assign({}, DEFAULT_SHORTCUTS);
      saveShortcuts(shortcuts);
    },
    findConflicts: findConflicts,
    comboLabel: comboLabel,
    normalizeCombo: normalizeCombo,
    open: open,
    close: close
  };
})();
