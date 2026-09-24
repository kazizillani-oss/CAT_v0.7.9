/* ==========================================================================
   FOMOJI — FX ENGINE
   Purely additive companion to fomoji-theme.js:
     - renders + animates the multi-set ascii art gallery (.ascii-gallery)
     - edge-swipe navigation between two arbitrary pages (data-swipe-left /
       data-swipe-right on <body>) — e.g. log in <-> create account
     - long-press context menu on any [data-longpress-menu] element
     - pull-to-refresh visual affordance on [data-pull-refresh] pages
     - swipe-to-dismiss on any .fx-swipe-dismissable element (e.g. the
       guest banner)
   Include after fomoji-theme.js and fomoji.css/fomoji-fx.css.
   ========================================================================== */
(() => {
  const ASCII_SETS = {
    cat: [
      ' /\\_/\\   fomoji · identity',
      '( o.o )  status ..... <span class="ascii-gallery-hi">online</span>',
      ' > ^ <   link ....... synced',
    ],
    orbit: [
      '    * . <span class="ascii-gallery-hi">CAT</span>',
      '  .   \\',
      '  fomoji--<span class="ascii-gallery-hi">core</span>',
      '  .   /',
      '    * . apps',
    ],
    signal: [
      '[fomoji] handshake  <span class="ascii-gallery-hi">ok</span>',
      '[fomoji] device     <span class="ascii-gallery-hi">trusted</span>',
      '[fomoji] session    <span class="ascii-gallery-hi">valid</span>',
      '[fomoji] cat        <span class="ascii-gallery-hi">connected</span>',
    ],
    wave: [
      '~ ~ . ~ ~ . ~ ~ . ~ ~',
      '  \\_ fomoji link _/',
      '~ ~ . ~ ~ . ~ ~ . ~ ~',
    ],
  };
  const ASCII_LABELS = { cat: 'cat', orbit: 'orbit', signal: 'signal', wave: 'wave' };

  function renderAsciiSet(pre, name) {
    const lines = ASCII_SETS[name] || ASCII_SETS.cat;
    pre.innerHTML = lines.map((l, i) =>
      `<span class="ascii-gallery-line" style="--line-delay:${(i * 0.16).toFixed(2)}s">${l}</span>`
    ).join('\n') + '<span class="ascii-cursor">▍</span>';
  }

  function initAsciiGalleries() {
    document.querySelectorAll('.ascii-gallery').forEach(gallery => {
      const pre = gallery.querySelector('.ascii-gallery-body');
      const tabs = gallery.querySelector('.ascii-gallery-tabs');
      if (!pre || !tabs || gallery.dataset.fxWired) return;
      gallery.dataset.fxWired = '1';

      const sets = (gallery.dataset.sets || 'cat,orbit,signal,wave').split(',').map(s => s.trim());
      tabs.innerHTML = sets.map((s, i) =>
        `<button type="button" class="ascii-gallery-tab${i === 0 ? ' is-active' : ''}" data-set="${s}">${ASCII_LABELS[s] || s}</button>`
      ).join('');

      renderAsciiSet(pre, sets[0]);

      let cycleTimer = null;
      function select(name) {
        tabs.querySelectorAll('.ascii-gallery-tab').forEach(b => b.classList.toggle('is-active', b.dataset.set === name));
        renderAsciiSet(pre, name);
      }
      tabs.addEventListener('click', (e) => {
        const btn = e.target.closest('.ascii-gallery-tab');
        if (!btn) return;
        clearInterval(cycleTimer);
        select(btn.dataset.set);
      });

      // gentle auto-cycle unless the user has interacted or asked for less motion
      if (document.documentElement.dataset.parallax !== 'off' && sets.length > 1) {
        let idx = 0;
        cycleTimer = setInterval(() => {
          idx = (idx + 1) % sets.length;
          select(sets[idx]);
        }, 5200);
      }
    });
  }

  // ------------------------------------------------------------------
  // Edge-swipe navigation between two specific pages
  // ------------------------------------------------------------------
  function initPageSwipeNav() {
    const left = document.body.dataset.swipeLeft;   // navigate here on swipe-left
    const right = document.body.dataset.swipeRight; // navigate here on swipe-right
    if (!left && !right) return;
    if (document.documentElement.dataset.gestures === 'off') return;

    let startX = 0, startY = 0, tracking = false;
    document.addEventListener('touchstart', (e) => {
      const t = e.touches[0];
      startX = t.clientX; startY = t.clientY; tracking = true;
    }, { passive: true });
    document.addEventListener('touchend', (e) => {
      if (!tracking) return;
      tracking = false;
      const t = e.changedTouches[0];
      const dx = t.clientX - startX, dy = t.clientY - startY;
      if (Math.abs(dx) < 80 || Math.abs(dx) < Math.abs(dy) * 1.6) return;
      const target = dx < 0 ? left : right;
      if (!target) return;
      showHint(dx < 0 ? 'left' : 'right');
      setTimeout(() => { window.location.href = target; }, 140);
    }, { passive: true });
  }

  function showHint(direction) {
    if (document.documentElement.classList.contains('reduce-motion')) return;
    const hint = document.createElement('div');
    hint.className = 'swipe-hint swipe-hint-' + direction;
    hint.setAttribute('aria-hidden', 'true');
    document.body.appendChild(hint);
    setTimeout(() => hint.remove(), 500);
  }

  // ------------------------------------------------------------------
  // Long-press context menu
  // Element declares: data-longpress-menu='[{"label":"Copy link","action":"copy"}]'
  // and listens for the "fx-longpress-action" custom event to handle it.
  // ------------------------------------------------------------------
  function initLongPress() {
    let menu = null;
    function closeMenu() { if (menu) { menu.classList.remove('is-open'); setTimeout(() => menu?.remove(), 150); menu = null; } }
    document.addEventListener('click', (e) => { if (menu && !e.target.closest('.fx-longpress-menu')) closeMenu(); });

    document.addEventListener('touchstart', (e) => {
      const el = e.target.closest('[data-longpress-menu]');
      if (!el) return;
      const touch = e.touches[0];
      const startX = touch.clientX, startY = touch.clientY;
      const timer = setTimeout(() => {
        navigator.vibrate?.(12);
        openMenu(el, startX, startY);
      }, 520);
      const cancel = () => clearTimeout(timer);
      el.addEventListener('touchend', cancel, { once: true });
      el.addEventListener('touchmove', cancel, { once: true });
    }, { passive: true });

    function openMenu(el, x, y) {
      closeMenu();
      let items;
      try { items = JSON.parse(el.dataset.longpressMenu); } catch { items = []; }
      if (!items.length) return;
      menu = document.createElement('div');
      menu.className = 'fx-longpress-menu';
      menu.style.left = Math.min(x, window.innerWidth - 200) + 'px';
      menu.style.top = Math.min(y, window.innerHeight - items.length * 40 - 20) + 'px';
      menu.innerHTML = items.map(it => `<button type="button" data-action="${it.action}">${it.label}</button>`).join('');
      document.body.appendChild(menu);
      requestAnimationFrame(() => menu.classList.add('is-open'));
      menu.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        el.dispatchEvent(new CustomEvent('fx-longpress-action', { detail: { action: btn.dataset.action } }));
        closeMenu();
      });
    }
  }

  // ------------------------------------------------------------------
  // Pull-to-refresh visual (body carries data-pull-refresh)
  // ------------------------------------------------------------------
  function initPullToRefresh() {
    if (document.body.dataset.pullRefresh === undefined) return;
    const host = document.querySelector('main') || document.body;
    if (getComputedStyle(host).position === 'static') host.style.position = 'relative';

    const indicator = document.createElement('div');
    indicator.className = 'fx-pulltorefresh';
    indicator.innerHTML = '<span class="fx-spin-glyph">↻</span><span>' + (document.body.dataset.pullRefreshLabel || 'refreshing') + '</span>';
    host.prepend(indicator);

    let startY = 0, pulling = false, fired = false;
    window.addEventListener('touchstart', (e) => {
      if (window.scrollY <= 0) { startY = e.touches[0].clientY; pulling = true; fired = false; }
    }, { passive: true });
    window.addEventListener('touchmove', (e) => {
      if (!pulling) return;
      const dy = e.touches[0].clientY - startY;
      if (dy > 64) indicator.classList.add('is-visible');
    }, { passive: true });
    window.addEventListener('touchend', () => {
      if (indicator.classList.contains('is-visible') && !fired) {
        fired = true;
        document.dispatchEvent(new CustomEvent('fx-pull-refresh'));
        setTimeout(() => indicator.classList.remove('is-visible'), 750);
      }
      pulling = false;
    }, { passive: true });
  }

  // ------------------------------------------------------------------
  // Swipe-to-dismiss for banners / alerts
  // ------------------------------------------------------------------
  function initSwipeDismiss() {
    document.querySelectorAll('.fx-swipe-dismissable').forEach(el => {
      if (el.dataset.fxWired) return;
      el.dataset.fxWired = '1';
      let startX = 0, dx = 0, tracking = false;
      el.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; tracking = true; el.classList.add('fx-swipe-dismissing'); }, { passive: true });
      el.addEventListener('touchmove', (e) => {
        if (!tracking) return;
        dx = e.touches[0].clientX - startX;
        if (dx > 0) el.style.transform = `translateX(${dx}px)`;
      }, { passive: true });
      el.addEventListener('touchend', () => {
        tracking = false;
        el.classList.remove('fx-swipe-dismissing');
        if (dx > 100) {
          el.classList.add('fx-swipe-dismissed');
          setTimeout(() => { el.style.display = 'none'; }, 260);
        } else {
          el.style.transform = '';
        }
        dx = 0;
      });
    });
  }

  function boot() {
    initAsciiGalleries();
    initPageSwipeNav();
    initLongPress();
    initPullToRefresh();
    initSwipeDismiss();
    document.addEventListener('fomoji-appearance-change', initAsciiGalleries);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
