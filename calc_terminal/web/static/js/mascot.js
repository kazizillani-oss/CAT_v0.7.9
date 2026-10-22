/**
 * FATTY CAT — Page Mascot Controller
 * Implements cursor tracking (9 head directions) and reaction states (9 expressions)
 * with zero per-frame animations, using sprite sheets via background-position.
 */
(function (global) {
  'use strict';

  var DIRECTIONS = [
    'up-left', 'up', 'up-right',
    'left', 'center', 'right',
    'down-left', 'down', 'down-right'
  ];

  var REACTIONS = [
    'blink', 'heart', 'sparkle',
    'surprised', 'wink', 'bashful',
    'sleepy', 'dizzy', 'delighted'
  ];

  // Clockwise starting from right (0 rad in atan2)
  var CLOCKWISE = [
    'right', 'down-right', 'down', 'down-left',
    'left', 'up-left', 'up', 'up-right'
  ];

  var SECTOR = (Math.PI * 2) / CLOCKWISE.length;
  var HYSTERESIS = 0.12;
  var DEAD_ZONE = 55;

  var PAYOFFS = ['heart', 'sparkle', 'delighted'];
  var BOOP_PAYOFF = 120;
  var BOOP_END = 560;
  var SQUASH_MS = 420;
  var DIZZY_AFTER = 4;
  var DIZZY_WINDOW = 1600;
  var DIZZY_END = 1100;
  var ACTIVITY_REACTIONS = {
    thinking: 'sleepy',
    working: 'wink',
    approval: 'bashful',
    success: 'heart',
    error: 'surprised'
  };

  var SQUASH = [
    { transform: 'scale(1, 1)', easing: 'ease-in' },
    { transform: 'scale(1.10, 0.86)', offset: 0.18, easing: 'ease-out' },
    { transform: 'scale(0.95, 1.08)', offset: 0.45, easing: 'ease-in-out' },
    { transform: 'scale(1.03, 0.97)', offset: 0.72, easing: 'ease-in-out' },
    { transform: 'scale(1, 1)' }
  ];

  function assetPath(file) {
    try { return new URL('./mascots/' + file, document.baseURI).href; }
    catch (e) { return './mascots/' + file; }
  }

  var PRESETS = {
    'fattycat': {
      name: 'Fatty Cat (Chubby & Cute)',
      directions: assetPath('fattycat-directions.webp?v=cat-aligned-20261010f'),
      reactions: assetPath('fattycat-reactions.webp?v=cat-aligned-20261010f')
    },
    'fattycat-riso': {
      name: 'Fatty Cat (Riso Style)',
      directions: assetPath('fattycat-riso-directions.webp'),
      reactions: assetPath('fattycat-riso-reactions.webp')
    },
    'otter': {
      name: 'Chibi Otter',
      directions: assetPath('otter-directions.webp'),
      reactions: assetPath('otter-reactions.webp')
    },
    'otter-riso': {
      name: 'Chibi Otter (Riso Style)',
      directions: assetPath('otter-riso-directions.webp'),
      reactions: assetPath('otter-riso-reactions.webp')
    }
  };


  function cellPos(index) {
    var x = (index % 3) * 50;
    var y = Math.floor(index / 3) * 50;
    return x + '% ' + y + '%';
  }

  function wrapAngle(angle) {
    return Math.atan2(Math.sin(angle), Math.cos(angle));
  }

  function MascotController(mountEl, options) {
    this.mount = mountEl;
    var saved = 'fattycat';
    try {
      saved = localStorage.getItem('fatty_page_mascot') || 'fattycat';
    } catch (e) {}

    this.options = Object.assign({
      character: saved,
      size: 40,
      label: 'Mascot'
    }, options || {});

    this.currentPresetKey = this.options.character;
    if (!PRESETS[this.currentPresetKey]) this.currentPresetKey = 'fattycat';
    this.direction = 'center';
    this.reaction = null;
    this.activity = 'idle';
    this.activityTimer = null;
    this.timers = [];
    this.boops = { count: 0, at: 0 };
    this.sector = -1;
    this.pointer = null;

    this._preloadAll();
    this._render();
    this._bindEvents();
  }

  MascotController.prototype._preloadAll = function () {
    try {
      Object.keys(PRESETS).forEach(function (k) {
        var p = PRESETS[k];
        var d = new Image(); d.src = p.directions;
        var r = new Image(); r.src = p.reactions;
      });
    } catch (e) {}
  };

  MascotController.prototype._applySheet = function (layer, url) {
    if (!layer || !url) return;
    layer.style.backgroundImage = 'url("' + url + '")';
    var testImg = new Image();
    var paths = [url];
    var file = url.split('/').pop().split(/[?#]/)[0];
    try {
      paths.push(new URL('/mascots/' + file, document.baseURI).href);
      paths.push(new URL('./mascots/' + file, document.baseURI).href);
    } catch (e) {}
    paths = paths.filter(function (path, index) { return paths.indexOf(path) === index; });
    var pathIndex = 0;
    testImg.onerror = function () {
      pathIndex += 1;
      if (pathIndex >= paths.length) return;
      layer.style.backgroundImage = 'url("' + paths[pathIndex] + '")';
      testImg.src = paths[pathIndex];
    };
    testImg.src = url;
  };

  MascotController.prototype._render = function () {
    var p = PRESETS[this.currentPresetKey] || PRESETS['fattycat'];
    var sz = this.options.size;

    this.mount.innerHTML = '';
    this.mount.classList.add('cct-mascot-wrapper');

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'cct-mascot-btn';
    btn.setAttribute('aria-label', 'Boop the ' + p.name);
    btn.title = p.name + ' (Click to boop)';
    btn.style.width = sz + 'px';
    btn.style.height = sz + 'px';
    btn.style.setProperty('--mascot-size', sz + 'px');

    var squash = document.createElement('span');
    squash.className = 'cct-mascot-squash';

    var dirLayer = document.createElement('span');
    dirLayer.className = 'cct-mascot-layer cct-mascot-dir';
    this._applySheet(dirLayer, p.directions);
    dirLayer.style.backgroundPosition = cellPos(DIRECTIONS.indexOf('center'));

    var reactLayer = document.createElement('span');
    reactLayer.className = 'cct-mascot-layer cct-mascot-react';
    this._applySheet(reactLayer, p.reactions);
    reactLayer.style.backgroundPosition = cellPos(0);
    reactLayer.style.opacity = '0';

    squash.appendChild(dirLayer);
    squash.appendChild(reactLayer);
    btn.appendChild(squash);

    this.mount.appendChild(btn);

    this.btn = btn;
    this.squash = squash;
    this.dirLayer = dirLayer;
    this.reactLayer = reactLayer;
  };

  MascotController.prototype.setCharacter = function (key) {
    if (!PRESETS[key]) return;
    this.currentPresetKey = key;
    try {
      localStorage.setItem('fatty_page_mascot', key);
    } catch (e) {}
    var p = PRESETS[key];
    this._applySheet(this.dirLayer, p.directions);
    this._applySheet(this.reactLayer, p.reactions);
    this.btn.title = p.name + ' (Click to boop)';
    this._updateVisuals();
  };

  MascotController.prototype.toggleNext = function () {
    var keys = Object.keys(PRESETS);
    var idx = keys.indexOf(this.currentPresetKey);
    var next = keys[(idx + 1) % keys.length];
    this.setCharacter(next);
  };

  MascotController.prototype._updateVisuals = function () {
    var dirIdx = DIRECTIONS.indexOf(this.direction);
    if (dirIdx < 0) dirIdx = 4;
    this.dirLayer.style.backgroundPosition = cellPos(dirIdx);

    var activityReaction = ACTIVITY_REACTIONS[this.activity];
    var visibleReaction = this.reaction || activityReaction || null;
    if (visibleReaction) {
      var reactIdx = REACTIONS.indexOf(visibleReaction);
      if (reactIdx < 0) reactIdx = 0;
      this.reactLayer.style.backgroundPosition = cellPos(reactIdx);
      this.reactLayer.style.opacity = '1';
      this.dirLayer.style.opacity = '0';
    } else {
      this.reactLayer.style.opacity = '0';
      this.dirLayer.style.opacity = '1';
    }
  };

  MascotController.prototype.setActivity = function (activity) {
    var allowed = ['idle', 'thinking', 'working', 'approval', 'success', 'error'];
    this.activity = allowed.indexOf(activity) >= 0 ? activity : 'idle';
    clearTimeout(this.activityTimer);
    this.btn.setAttribute('aria-label', this.activity === 'idle'
      ? 'Boop the ' + PRESETS[this.currentPresetKey].name
      : PRESETS[this.currentPresetKey].name + ' is ' + this.activity);
    this._updateVisuals();
    if (this.activity === 'success' || this.activity === 'error') {
      var self = this;
      this.activityTimer = setTimeout(function () {
        self.setActivity('idle');
      }, this.activity === 'success' ? 1500 : 2200);
    }
  };

  MascotController.prototype.boop = function () {
    var self = this;
    this.timers.forEach(clearTimeout);
    this.timers = [];

    function later(ms, next) {
      self.timers.push(setTimeout(function () {
        self.reaction = next;
        self._updateVisuals();
      }, ms));
    }

    var now = Date.now();
    this.boops.count = (now - this.boops.at < DIZZY_WINDOW) ? this.boops.count + 1 : 1;
    this.boops.at = now;

    if (this.boops.count >= DIZZY_AFTER) {
      this.boops.count = 0;
      this.reaction = 'dizzy';
      this._updateVisuals();
      later(DIZZY_END, null);
    } else {
      this.reaction = 'blink';
      this._updateVisuals();
      var payoff = PAYOFFS[(this.boops.count - 1) % PAYOFFS.length];
      later(BOOP_PAYOFF, payoff);
      later(BOOP_END, null);
    }

    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if (this.squash && this.squash.animate) {
        this.squash.animate(SQUASH, { duration: SQUASH_MS, easing: 'linear' });
      }
    }
  };

  MascotController.prototype._aim = function () {
    if (!this.pointer || this.reaction) return;

    var rect = this.btn.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;
    var dx = this.pointer.x - cx;
    var dy = this.pointer.y - cy;
    var dist = Math.hypot(dx, dy);

    var nextDir = 'center';
    var nextSector = -1;

    if (dist >= DEAD_ZONE) {
      var angle = Math.atan2(dy, dx);
      if (angle < 0) angle += Math.PI * 2;

      var currentAngle = this.sector >= 0 ? this.sector * SECTOR : null;
      var diff = currentAngle !== null ? Math.abs(wrapAngle(angle - currentAngle)) : Infinity;

      if (this.sector >= 0 && diff < SECTOR / 2 + HYSTERESIS) {
        nextSector = this.sector;
      } else {
        nextSector = Math.floor((angle + SECTOR / 2) / SECTOR) % CLOCKWISE.length;
      }

      nextDir = CLOCKWISE[nextSector];
    }

    if (nextDir !== this.direction) {
      this.direction = nextDir;
      this.sector = nextSector;
      this._updateVisuals();
    }
  };

  MascotController.prototype._bindEvents = function () {
    var self = this;
    var aimFrame = 0;

    this.btn.addEventListener('click', function (e) {
      e.preventDefault();
      self.boop();
    });

    var hasFinePointer = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    var embeddedRenderer = document.documentElement.classList.contains('cat-browser-renderer');
    if (!embeddedRenderer && (this.options.trackPointer === true || (this.options.trackPointer !== false && hasFinePointer))) {
      window.addEventListener('pointermove', function (e) {
        self.pointer = { x: e.clientX, y: e.clientY };
        if (!aimFrame) {
          aimFrame = window.requestAnimationFrame(function () {
            aimFrame = 0;
            self._aim();
          });
        }
      }, { passive: true });

      window.addEventListener('scroll', function () {
        if (!aimFrame) {
          aimFrame = window.requestAnimationFrame(function () {
            aimFrame = 0;
            self._aim();
          });
        }
      }, { passive: true });

      document.addEventListener('visibilitychange', function () {
        if (document.hidden && aimFrame) {
          window.cancelAnimationFrame(aimFrame);
          aimFrame = 0;
        }
      });
    }
  };

  global.FattyMascot = {
    PRESETS: PRESETS,
    init: function (container, options) {
      var el = (typeof container === 'string') ? document.querySelector(container) : container;
      if (!el) return null;
      return new MascotController(el, options);
    }
  };
})(window);
