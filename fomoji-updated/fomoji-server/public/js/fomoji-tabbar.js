/* ==========================================================================
   FOMOJI — Tab Bar Studio
   Frontend-only, same honesty rule as the rest of Fomoji: nothing here talks
   to a server, nothing here can execute arbitrary script. Every tab points
   at a fixed, named action from ACTIONS below — customization can reorder,
   relabel, re-icon, hide, or reassign tabs, but it can never introduce a new
   capability the app doesn't already have. Persists to localStorage
   per-browser. Include on every page that renders <nav class="tabbar">.

   Exposes window.FomojiTabbar:
     ICONS                      -> { key: {svg, ascii, emoji, label} }
     ACTIONS                    -> [{ id, label, group }]  (safe to list in a <select>)
     get()                      -> { tabs:[...], position:'bottom'|'top' }
     getTabs()                  -> resolved tab list (defaults filled in)
     addTab({label, icon, action}) -> new tab id
     updateTab(id, patch)       -> rename / re-icon / reassign action
     removeTab(id)              -> false if blocked (protected or last visible)
     setHidden(id, bool)        -> false if it would leave zero visible tabs
     setPinned(id, bool)
     reorder(idsInOrder)
     setPosition('bottom'|'top')
     resetToDefault()
     render()                   -> re-render this page's <nav class="tabbar"> now
   ========================================================================== */
(function () {
  'use strict';

  var KEY = 'fomoji_tabbar_v1';
  var HOME_ID = 'home'; // always present, always visible — the guaranteed way back

  /* ---- icon registry: every icon a tab can use, same outline/ascii/emoji
     triple the rest of the app already themes via [data-icons] on <html> ---- */
  var ICONS = {
    home:    { label: 'Home',      ascii: '[~]', emoji: '🏠', svg: '<path d="M4 11.5 12 4l8 7.5"/><path d="M6 10v9h12v-9"/>' },
    about:   { label: 'About',     ascii: '[i]', emoji: '🌀', svg: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><circle cx="12" cy="7.6" r="0.9" fill="currentColor" stroke="none"/>' },
    person:  { label: 'Profile',   ascii: '[@]', emoji: '🙂', svg: '<circle cx="12" cy="8.5" r="3.4"/><path d="M5 20c1.2-3.6 4-5.4 7-5.4s5.8 1.8 7 5.4"/>' },
    shield:  { label: 'Security',  ascii: '[#]', emoji: '🛡️', svg: '<path d="M12 3.5 5 6v6c0 4.5 3 7.7 7 8.5 4-.8 7-4 7-8.5V6l-7-2.5Z"/>' },
    devices: { label: 'Devices',   ascii: '[=]', emoji: '💻', svg: '<rect x="3" y="5" width="13" height="9" rx="1.5"/><path d="M8 18h6"/><rect x="17" y="9" width="4" height="7" rx="1"/>' },
    apps:    { label: 'Apps',      ascii: '[+]', emoji: '🧩', svg: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>' },
    help:    { label: 'Help',      ascii: '[?]', emoji: '❓', svg: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7v.3"/><circle cx="12" cy="16.7" r="0.4" fill="currentColor" stroke="none"/>' },
    star:    { label: 'Star',      ascii: '[*]', emoji: '⭐', svg: '<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.2 1 5.9-5.2-2.8-5.2 2.8 1-5.9-4.3-4.2 5.9-.8Z"/>' },
    bolt:    { label: 'Bolt',      ascii: '[!]', emoji: '⚡', svg: '<path d="M13 3 5 13h5l-1 8 8-11h-5l1-7Z"/>' },
    palette: { label: 'Theme',     ascii: '[%]', emoji: '🎨', svg: '<circle cx="12" cy="12" r="9"/><circle cx="8.5" cy="10" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="8" r="1.2" fill="currentColor" stroke="none"/><circle cx="15.5" cy="10" r="1.2" fill="currentColor" stroke="none"/>' },
    lock:    { label: 'Privacy',   ascii: '[&]', emoji: '🔒', svg: '<rect x="5" y="10.5" width="14" height="9" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>' },
    cat:     { label: 'CAT',       ascii: '[c]', emoji: '🐱', svg: '<path d="M5 9 3 4l4.5 2.3M19 9l2-5-4.5 2.3M5 9c0-2.8 3-4.5 7-4.5s7 1.7 7 4.5-2.5 8-7 8-7-5.2-7-8Z"/><circle cx="9.3" cy="10.5" r=".6" fill="currentColor" stroke="none"/><circle cx="14.7" cy="10.5" r=".6" fill="currentColor" stroke="none"/>' },
    grid:    { label: 'Palette',   ascii: '[:]', emoji: '🔎', svg: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m19 19-4-4"/>' }
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

  /* ---- action registry: the ONLY things a tab is allowed to do. No custom
     tab can execute arbitrary code — it can only point at one of these. ---- */
  var ACTIONS = [
    { id: 'home',       label: 'Open Home',            group: 'Navigate',    go: 'home.html' },
    { id: 'about',      label: 'Open About',           group: 'Navigate',    go: 'about.html' },
    { id: 'settings',   label: 'Open Settings',        group: 'Navigate',    go: 'settings.html' },
    { id: 'help',       label: 'Open Help',            group: 'Navigate',    go: 'help.html' },
    { id: 'cat',        label: 'Open CAT',             group: 'Navigate',    go: 'home.html' },
    { id: 'security',   label: 'Open Security',        group: 'Account',     go: 'settings.html#security' },
    { id: 'connected',  label: 'Open Connected apps',  group: 'Account',     go: 'settings.html#connected' },
    { id: 'privacy',    label: 'Open Privacy',         group: 'Account',     go: 'settings.html#privacy' },
    { id: 'appearance', label: 'Open Theme Studio',    group: 'Personalize', go: 'settings.html#appearance' },
    { id: 'navigation', label: 'Open Navigation',      group: 'Personalize', go: 'settings.html#navigation' },
    { id: 'shortcuts',  label: 'Open Shortcuts',       group: 'Personalize', go: 'settings.html#shortcuts' },
    { id: 'palette',    label: 'Open Command Palette', group: 'Personalize', run: function () { if (window.FomojiCommands) FomojiCommands.open(); } },
    { id: 'signOut',    label: 'Sign out',             group: 'Account',     run: function () {
        if (window.FomojiSignOut && typeof FomojiSignOut.trigger === 'function') {
          FomojiSignOut.trigger(function () { go('welcome.html'); });
        } else {
          if (window.FomojiAPI && typeof FomojiAPI.logout === 'function') { try { FomojiAPI.logout(); } catch (e) {} }
          go('welcome.html');
        }
      } }
  ];
  var ACTION_MAP = {};
  ACTIONS.forEach(function (a) { ACTION_MAP[a.id] = a; });

  var DEFAULT_TABS = [
    { id: 'home',     label: 'Home',  icon: 'home',   action: 'home',     hidden: false, pinned: true },
    { id: 'me',       label: 'Me',    icon: 'person', action: 'settings', hidden: false, pinned: false }
  ];
  var DEFAULTS = { tabs: DEFAULT_TABS, position: 'bottom' };

  function uid() { return 't' + Math.random().toString(36).slice(2, 9); }

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return clone(DEFAULTS);
      var parsed = JSON.parse(raw);
      if (!parsed || !Array.isArray(parsed.tabs) || !parsed.tabs.length) return clone(DEFAULTS);
      // guarantee the home tab always exists, is pinned, and is visible —
      // it's the one action customization can never remove or hide.
      var hasHome = parsed.tabs.some(function (t) { return t.id === HOME_ID; });
      if (!hasHome) parsed.tabs.unshift(clone(DEFAULT_TABS[0]));
      parsed.tabs = parsed.tabs.map(function (t) {
        if (t.id === HOME_ID) { t.pinned = true; t.hidden = false; }
        return t;
      });
      if (parsed.position !== 'top' && parsed.position !== 'bottom') parsed.position = 'bottom';
      return parsed;
    } catch (e) {
      return clone(DEFAULTS);
    }
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function save(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }
  function emit() {
    document.dispatchEvent(new CustomEvent('fomoji-tabbar-change', { detail: clone(state) }));
  }

  var state = load();

  function visibleCount() { return state.tabs.filter(function (t) { return !t.hidden; }).length; }

  /* ---- rendering ---- */
  function currentPage() { return (location.pathname.split('/').pop() || 'home.html'); }

  function tabTargetPage(tab) {
    var action = ACTION_MAP[tab.action];
    if (!action || !action.go) return null;
    return action.go.split('#')[0];
  }

  function renderTabMarkup(tab) {
    var icon = ICONS[tab.icon] || ICONS.star;
    var action = ACTION_MAP[tab.action] || ACTION_MAP.home;
    var isActive = tabTargetPage(tab) === currentPage();
    var tag = action.go ? 'a' : 'button';
    var attrs = 'class="tab' + (isActive ? ' is-active' : '') + '" data-tab-id="' + tab.id + '"' +
      (action.go ? ' href="' + action.go + '"' + (isActive ? ' aria-current="page"' : '') : ' type="button"') +
      ' data-ascii-glyph="' + icon.ascii + '" data-emoji-glyph="' + icon.emoji + '"';
    var label = String(tab.label || icon.label).replace(/[<>&]/g, function (c) { return { '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]; });
    var closeBtn = (!tab.pinned)
      ? '<button type="button" class="tab-close" data-close-tab="' + tab.id + '" aria-label="Remove tab">&times;</button>'
      : '';
    return '<' + tag + ' ' + attrs + '>' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + icon.svg + '</svg>' +
      '<span class="tab-label">' + label + '</span>' +
      closeBtn +
      '</' + tag + '>';
  }

  function render() {
    var nav = document.querySelector('nav.tabbar');
    if (!nav) return;

    var visible = state.tabs.filter(function (t) { return !t.hidden; });
    nav.innerHTML = visible.map(renderTabMarkup).join('');

    nav.querySelectorAll('.tab[type="button"]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        if (e.target.closest('.tab-close')) return;
        var tab = state.tabs.filter(function (t) { return t.id === btn.dataset.tabId; })[0];
        var action = tab && ACTION_MAP[tab.action];
        if (action && typeof action.run === 'function') action.run();
      });
    });

    nav.querySelectorAll('.tab-close').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var tabId = btn.dataset.closeTab;
        removeTab(tabId);
      });
    });

    var topbar = document.querySelector('.topbar');
    var spacer = document.querySelector('.tabbar-spacer');
    document.documentElement.setAttribute('data-tabbar-pos', state.position);
    if (state.position === 'top') {
      if (topbar && topbar.nextElementSibling !== nav) topbar.insertAdjacentElement('afterend', nav);
      if (spacer) spacer.style.display = 'none';
    } else {
      if (document.body.lastElementChild !== nav && nav.parentElement === document.body) {
        document.body.appendChild(nav);
      }
      if (spacer) spacer.style.display = '';
    }
  }

  /* ---- public mutation API ---- */
  function getTabs() { return clone(state.tabs); }

  function addTab(opts) {
    var id = uid();
    state.tabs.push({
      id: id,
      label: (opts && opts.label) || 'New tab',
      icon: (opts && ICONS[opts.icon]) ? opts.icon : 'star',
      action: (opts && ACTION_MAP[opts.action]) ? opts.action : 'home',
      hidden: false,
      pinned: false
    });
    save(state); emit(); render();
    return id;
  }

  function updateTab(id, patch) {
    var tab = state.tabs.filter(function (t) { return t.id === id; })[0];
    if (!tab) return false;
    if (patch.label != null) tab.label = String(patch.label).slice(0, 24) || tab.label;
    if (patch.icon != null && ICONS[patch.icon]) tab.icon = patch.icon;
    if (patch.action != null && ACTION_MAP[patch.action]) tab.action = patch.action;
    save(state); emit(); render();
    return true;
  }

  function removeTab(id) {
    if (id === HOME_ID) return false; // the one tab that's never removable
    var tab = state.tabs.filter(function (t) { return t.id === id; })[0];
    if (!tab || tab.pinned) return false;
    if (state.tabs.length <= 1) return false;
    state.tabs = state.tabs.filter(function (t) { return t.id !== id; });
    save(state); emit(); render();
    return true;
  }

  function setHidden(id, hidden) {
    var tab = state.tabs.filter(function (t) { return t.id === id; })[0];
    if (!tab) return false;
    if (tab.pinned && hidden) return false; // pinned tabs (home) can't be hidden
    if (hidden && visibleCount() <= 1) return false; // always keep at least one tab visible
    tab.hidden = hidden;
    save(state); emit(); render();
    return true;
  }

  function setPinned(id, pinned) {
    var tab = state.tabs.filter(function (t) { return t.id === id; })[0];
    if (!tab) return false;
    tab.pinned = !!pinned;
    save(state); emit(); render();
    return true;
  }

  function reorder(idsInOrder) {
    var byId = {};
    state.tabs.forEach(function (t) { byId[t.id] = t; });
    var next = idsInOrder.map(function (id) { return byId[id]; }).filter(Boolean);
    state.tabs.forEach(function (t) { if (idsInOrder.indexOf(t.id) === -1) next.push(t); });
    state.tabs = next;
    save(state); emit(); render();
  }

  function setPosition(pos) {
    state.position = pos === 'top' ? 'top' : 'bottom';
    save(state); emit(); render();
  }

  function resetToDefault() {
    state = clone(DEFAULTS);
    save(state); emit(); render();
  }

  window.FomojiTabbar = {
    ICONS: ICONS,
    ACTIONS: ACTIONS.map(function (a) { return { id: a.id, label: a.label, group: a.group }; }),
    HOME_ID: HOME_ID,
    get: function () { return clone(state); },
    getTabs: getTabs,
    addTab: addTab,
    updateTab: updateTab,
    removeTab: removeTab,
    setHidden: setHidden,
    setPinned: setPinned,
    reorder: reorder,
    setPosition: setPosition,
    resetToDefault: resetToDefault,
    render: render,
    runAction: function (id) {
      var action = ACTION_MAP[id];
      if (!action) return false;
      if (action.go) go(action.go);
      else if (typeof action.run === 'function') action.run();
      return true;
    }
  };

  function boot() { render(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
