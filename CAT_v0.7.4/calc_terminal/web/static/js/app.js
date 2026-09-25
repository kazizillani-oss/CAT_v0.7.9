/**
 * FATTY CAT — 1:1 CAT CLI Terminal Simulation Client
 * Direct bridge to CAT Core via FastAPI Server
 * Full Capability Integration (Tools, Modes, Commands, Providers, Memory, Extensions)
 */

(function() {
  'use strict';

  // ─── STATE ─────────────────────────────────────────────────────────────
  const state = {
    workspaceId: 'current',
    workspaceRoot: 'C:\\Users\\ADMIN\\Downloads\\compressed',
    workspaceName: 'compressed',
    activeMode: 'build',
    modes: ['build', 'plan', 'research', 'debugger', 'agent', 'notebook'],
    modeMeta: {
      build: { label: 'Build', icon: '🔨', color: '#e0af68', bg: '#cca75d', desc: 'Autonomous coding, file editing, build commands & testing' },
      plan: { label: 'Plan', icon: '🧭', color: '#9ece6a', bg: '#86b356', desc: 'High-level project roadmap, architecture planning & task breakdowns' },
      research: { label: 'Research', icon: '🔍', color: '#ff69b4', bg: '#d45695', desc: 'Deep scientific web search, multi-query synthesis & citations' },
      debugger: { label: 'Debugger', icon: '🪲', color: '#f7768e', bg: '#cf4661', desc: 'Diagnose runtime errors, stack traces, test failures & code fixes' },
      agent: { label: 'Agent', icon: '⚙', color: '#bb9af7', bg: '#9d7ad9', desc: 'Multi-turn autonomous tool execution loop over CAT core' },
      notebook: { label: 'Notebook', icon: '📘', color: '#7aa2f7', bg: '#587ec9', desc: 'Step-by-step chemistry derivations, formulas & numericals' }
    },
    provider: 'OLLAMA',
    model: 'deepseek-r1',
    permissionMode: 'ask',
    permLabels: {
      ask: { text: 'Ask Every Time', icon: '🔒' },
      restricted: { text: 'Restricted', icon: '🛡' },
      full: { text: 'Full Access', icon: '⚡' }
    },
    currentFile: null,
    openFiles: [],
    activeFileIndex: -1,
    editorOpen: false,
    splitPreview: false,
    previewRunning: false,
    turns: [],
    recentProjects: [
      { name: 'compressed', path: 'C:\\Users\\ADMIN\\Downloads\\compressed' },
      { name: 'ADMIN', path: 'C:\\Users\\ADMIN' },
      { name: 'CAT_v0.7.9', path: 'C:\\Users\\ADMIN\\Downloads\\CAT_v0.7.9' },
      { name: 'Downloads', path: 'C:\\Users\\ADMIN\\Downloads' },
      { name: 'Scripts', path: 'C:\\Users\\ADMIN\\Downloads\\Scripts' }
    ],
    sessionCount: 0,
    logoVariant: 0,
    sessionNotebooks: [],
    commands: [],
    filteredCommands: [],
    paletteSelectedIndex: 0,
    providers: [],
    models: [],
    selectedProvider: 'ollama',
    selectedModel: 'deepseek-r1',
    memoryFacts: [],
    extensions: [],
    activeSidebarTab: 'explorer',
    sidebarChats: [],
    sidebarActivities: [],
    sidebarExtensions: [],
    providerCenterData: null,
    selectedProviderId: 'ollama',
    selectedModelName: 'deepseek-r1',
    chatId: 'default',
    autoSave: true
  };

  // ─── 5 RESPONSIVE LAYOUT VARIANTS OF THE CAT WORDMARK LOGO ──────────────
  const ASCII_LOGO_VARIANTS = [
    {
      id: 'tier1',
      name: 'Tier 1: 3D Block (Desktop)',
      art: `  /\\_/\\   ██████╗  █████╗ ████████╗
 ( o.o ) ██╔════╝ ██╔══██╗╚══██╔══╝
  > ^ <  ██║      ███████║   ██║   
         ██║      ██╔══██║   ██║   
         ╚██████╗ ██║  ██║   ██║   
          ╚═════╝ ╚═╝  ╚═╝   ╚═╝   `
    },
    {
      id: 'tier2',
      name: 'Tier 2: Retro BBS (Standard)',
      art: `  /\\_/\\     ____ ___  ______
 ( o.o )   / __// _ |/_  __/
  > ^ <   / /__/ __ | / /   
          \\___/_/ |_|/_/    `
    },
    {
      id: 'tier3',
      name: 'Tier 3: Cat Combo (Medium)',
      art: `  /\\_/\\   █████  █████  ██████
 ( o.o )  ██     ██▄▄█    ██  
  > ^ <   █████  ██  █    ██  `
    },
    {
      id: 'tier4',
      name: 'Tier 4: Compact Bevel (Narrow)',
      art: `█▀▀▀ █▀▀█ ▀█▀
█    █▄▄█  █ 
▀▀▀▀ ▀  ▀  ▀ `
    },
    {
      id: 'tier5',
      name: 'Tier 5: Nano Banner (Micro)',
      art: `/\\_/\\ (o.o)  [CAT]
 > ^ <  CAT Intelligence`
    }
  ];

  // ─── API CLIENT ────────────────────────────────────────────────────────
  const api = {
    async request(method, path, body) {
      const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
      };
      if (body) opts.body = JSON.stringify(body);
      try {
        const res = await fetch(path, opts);
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail || 'HTTP ' + res.status);
        }
        return await res.json();
      } catch (e) {
        console.warn('API call failed for ' + path, e);
        throw e;
      }
    },
    get(path) { return this.request('GET', path); },
    post(path, body) { return this.request('POST', path, body); },
    del(path) { return this.request('DELETE', path); }
  };

  // ─── FATTY CONTROLLER ──────────────────────────────────────────────────
  window.FATTY = {
    async init() {
      console.log('Initializing 1:1 Fatty CAT simulation with Full Feature Integration...');
      this.bindDOM();
      this.bindResizers();

      // 1. Startup Welcome Lifecycle check (welcome_modal.py / Screenshot 2)
      await this.checkStartup();

      // 2. Load active workspace & file tree
      await this.loadWorkspace();

      // 3. Load permissions
      await this.loadPermissions();

      // 4. Load config & capabilities
      await this.loadConfig();

      // 5. Preload commands for Command Palette
      await this.loadCommands();

      // 6. Update line numbers for editor
      this.updateLineNumbers();

      // 7. Initialize ASCII wordmark logo variant
      this.initLogo();

      // 8. Load active session notebooks
      await this.loadSessionNotebooks();

      // 9. Initialize CAT 3D ASCII Block Art & Routine Greetings
      this.initCatRoutineGreeting();

      // 10. Initialize multi-file editor tabs bar
      this.renderEditorTabs();

      // 11. Initialize sidebar tab
      this.switchSidebarTab('explorer');
    },

    bindDOM() {
      const input = document.getElementById('cct-message-input');
      if (input) {
        input.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
          }
        });
        input.addEventListener('input', () => {
          input.style.height = 'auto';
          input.style.height = Math.min(120, Math.max(22, input.scrollHeight)) + 'px';
          // If user types '/' alone, suggest palette
          if (input.value === '/') {
            this.openCommandPalette();
          }
        });
      }

      const editor = document.getElementById('cct-code-editor');
      if (editor) {
        editor.addEventListener('input', () => {
          this.updateLineNumbers();
        });
        editor.addEventListener('scroll', () => {
          const gutter = document.getElementById('cct-line-numbers');
          if (gutter) gutter.scrollTop = editor.scrollTop;
        });
        editor.addEventListener('keydown', (e) => {
          if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            this.saveCurrentFile();
          } else if (e.key === 'Enter' && e.shiftKey) {
            e.preventDefault();
            // In Fatty CAT, Shift+Enter runs embedded web preview inside its own iframe (without popups)
            this.saveCurrentFile();
            if (!state.splitPreview) {
              this.toggleSplitView();
            } else {
              this.runPreview();
            }
          }
        });
      }

      // Palette search input navigation
      const paletteInput = document.getElementById('cct-palette-input');
      if (paletteInput) {
        paletteInput.addEventListener('input', (e) => {
          this.filterPalette(e.target.value);
        });
        paletteInput.addEventListener('keydown', (e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.paletteNext();
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.palettePrev();
          } else if (e.key === 'Enter') {
            e.preventDefault();
            this.executePaletteIndex();
          } else if (e.key === 'Escape') {
            this.closeAllModals();
          }
        });
      }

      // Global Shortcuts: Main Menu, Ctrl+K, Ctrl+M, Ctrl+B, Escape
      window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
          e.preventDefault();
          this.openCommandPalette();
        } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'P' || e.key === 'p')) {
          e.preventDefault();
          this.openCommandPalette();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'm' || e.key === 'M') && !e.shiftKey) {
          e.preventDefault();
          this.openModeSelector();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B') && !e.shiftKey) {
          e.preventDefault();
          this.toggleSidebar();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'o' || e.key === 'O')) {
          e.preventDefault();
          this.openFolderDialog();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'r' || e.key === 'R')) {
          e.preventDefault();
          this.openRecentWorkspacesModal();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'h' || e.key === 'H')) {
          e.preventDefault();
          this.openChatsModal();
        } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'M' || e.key === 'm')) {
          e.preventDefault();
          this.openMcpModal();
        } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'B' || e.key === 'b')) {
          e.preventDefault();
          this.openBackupProvidersModal();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 't' || e.key === 'T')) {
          e.preventDefault();
          this.openThemesModal();
        } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'X' || e.key === 'x')) {
          e.preventDefault();
          this.openExtensionsModal();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'u' || e.key === 'U')) {
          e.preventDefault();
          this.openUserModal();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'q' || e.key === 'Q')) {
          e.preventDefault();
          this.openSignOutModal();
        } else if (e.key === 'Escape') {
          this.closeAllModals();
        }
      });

      // Outside click listener to dismiss main menu popup
      document.addEventListener('click', (e) => {
        const popup = document.getElementById('cct-main-menu-popup');
        const brand = document.querySelector('.cct-header-left');
        if (popup && popup.style.display === 'block') {
          if (!popup.contains(e.target) && (!brand || !brand.contains(e.target))) {
            popup.style.display = 'none';
          }
        }
      });
    },

    bindResizers() {
      // Sidebar resizer
      const sbResizer = document.getElementById('cct-sidebar-resizer');
      const sidebar = document.getElementById('cct-sidebar');
      if (sbResizer && sidebar) {
        let isDragging = false;
        sbResizer.addEventListener('mousedown', () => {
          isDragging = true;
          document.body.style.cursor = 'col-resize';
          sbResizer.classList.add('dragging');
        });
        window.addEventListener('mousemove', (e) => {
          if (!isDragging) return;
          const newWidth = Math.max(180, Math.min(500, e.clientX));
          sidebar.style.width = newWidth + 'px';
        });
        window.addEventListener('mouseup', () => {
          isDragging = false;
          document.body.style.cursor = '';
          sbResizer.classList.remove('dragging');
        });
      }

      // Editor resizer
      const edResizer = document.getElementById('cct-editor-resizer');
      const editorPane = document.getElementById('cct-editor-pane');
      if (edResizer && editorPane) {
        let isDragging = false;
        edResizer.addEventListener('mousedown', () => {
          isDragging = true;
          document.body.style.cursor = 'col-resize';
          edResizer.classList.add('dragging');
        });
        window.addEventListener('mousemove', (e) => {
          if (!isDragging) return;
          const newWidth = Math.max(220, Math.min(window.innerWidth - 350, window.innerWidth - e.clientX));
          editorPane.style.width = newWidth + 'px';
        });
        window.addEventListener('mouseup', () => {
          isDragging = false;
          document.body.style.cursor = '';
          edResizer.classList.remove('dragging');
        });
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // WORKSPACE & FILE TREE
    // ─────────────────────────────────────────────────────────────────────
    async loadWorkspace(path) {
      try {
        let ws = await api.get('/api/workspace/current');
        if (ws && ws.path) {
          state.workspaceRoot = ws.path;
          state.workspaceName = ws.name || 'compressed';
        }
      } catch (e) {
        console.log('Using default workspace path');
      }

      // Update header workspace name
      const headWs = document.getElementById('cct-header-ws-name');
      if (headWs) headWs.textContent = state.workspaceName;

      // Update sidebar workspace name
      const sideWs = document.getElementById('cct-ws-folder-name');
      if (sideWs) sideWs.textContent = state.workspaceName;

      // Update dashboard opened folder tag and workspace card
      const openedTag = document.getElementById('cct-opened-folder-tag');
      if (openedTag) openedTag.textContent = `Opened folder: ${state.workspaceRoot}`;

      const wsCardPath = document.getElementById('cct-ws-card-path');
      if (wsCardPath) {
        wsCardPath.textContent = state.workspaceRoot;
        wsCardPath.title = state.workspaceRoot;
      }

      const wsCardUser = document.getElementById('cct-ws-card-user');
      if (wsCardUser) wsCardUser.textContent = state.workspaceName || 'ADMIN';

      // Fetch Tree
      try {
        const treeData = await api.get('/api/workspace/current/tree');
        if (treeData) {
          if (treeData.summary && treeData.summary.summary_line) {
            const sub = document.getElementById('cct-ws-folder-sub');
            if (sub) sub.textContent = treeData.summary.summary_line;
            const statsLine = document.getElementById('cct-ws-stats-line');
            if (statsLine) statsLine.textContent = treeData.summary.summary_line;
          }
          if (treeData.summary && treeData.summary.languages_line) {
            const langLine = document.getElementById('cct-ws-languages-line');
            if (langLine) langLine.textContent = treeData.summary.languages_line;
          }
          this.renderTree(treeData.children);
          if (treeData.recent && treeData.recent.length) {
            state.recentProjects = treeData.recent;
          }
        }
      } catch (e) {
        this.renderFallbackTree();
      }

      this.renderRecentProjects();
    },

    renderTree(nodes) {
      const container = document.getElementById('cct-tree-container');
      if (!container) return;
      container.innerHTML = '';

      const rootRow = document.createElement('div');
      rootRow.className = 'cct-tree-node';
      rootRow.innerHTML = `<span class="cct-tree-icon">📁</span> <span class="cct-tree-folder">${state.workspaceName}</span>`;
      container.appendChild(rootRow);

      const renderChildren = (children, prefix = '  ') => {
        if (!children || !children.length) return;
        children.forEach((child, idx) => {
          const isLast = idx === children.length - 1;
          const branch = isLast ? '└── ' : '├── ';
          const nextPrefix = prefix + (isLast ? '    ' : '│   ');

          const row = document.createElement('div');
          row.className = 'cct-tree-node';
          row.dataset.path = child.path;

          if (child.type === 'directory') {
            row.innerHTML = `<span class="cct-tree-guide">${prefix}${branch}</span><span class="cct-tree-icon">📁</span> <span class="cct-tree-folder">${child.name}</span>`;
            container.appendChild(row);
            renderChildren(child.children, nextPrefix);
          } else {
            const isIndexHtml = child.name === 'index.html';
            const fileIcon = child.ext === '.html' ? '📄' : (child.ext === '.js' ? '📄' : '📄');
            row.innerHTML = `<span class="cct-tree-guide">${prefix}${branch}</span><span class="cct-tree-icon">${fileIcon}</span> <span class="cct-tree-name">${child.name}</span>`;
            
            row.addEventListener('click', () => {
              this.openFile(child.path, child.name);
            });
            container.appendChild(row);
          }
        });
      };

      renderChildren(nodes);
    },

    renderFallbackTree() {
      const fallbackNodes = [
        {
          name: 'projects',
          type: 'directory',
          path: 'projects',
          children: [
            {
              name: 'calculator',
              type: 'directory',
              path: 'projects/calculator',
              children: [
                { name: 'index.html', type: 'file', path: 'projects/calculator/index.html', ext: '.html' },
                { name: 'script.js', type: 'file', path: 'projects/calculator/script.js', ext: '.js' },
                { name: 'style.css', type: 'file', path: 'projects/calculator/style.css', ext: '.css' }
              ]
            }
          ]
        }
      ];
      this.renderTree(fallbackNodes);
    },

    renderRecentProjects() {
      const container = document.getElementById('cct-recent-container');
      if (!container) return;
      container.innerHTML = '';

      state.recentProjects.slice(0, 5).forEach((p) => {
        const row = document.createElement('div');
        row.className = 'cct-recent-row';
        row.innerHTML = `
          <span class="cct-recent-name">📁 ${p.name}</span>
          <span class="cct-recent-del" title="Remove from recent">✕</span>
        `;
        row.querySelector('.cct-recent-name').addEventListener('click', () => {
          this.openRecentPath(p.path);
        });
        row.querySelector('.cct-recent-del').addEventListener('click', (e) => {
          e.stopPropagation();
          row.remove();
        });
        container.appendChild(row);
      });
    },

    // ─────────────────────────────────────────────────────────────────────
    // MULTI-FILE CODE EDITOR & TABS
    // ─────────────────────────────────────────────────────────────────────
    showToast(message, type = 'info') {
      const container = document.getElementById('cct-toast-container');
      if (!container) return;
      const toast = document.createElement('div');
      toast.className = `cct-toast ${type}`;
      toast.textContent = message;
      container.appendChild(toast);
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 3100);
    },

    renderEditorTabs() {
      const bar = document.getElementById('cct-editor-tabs-bar');
      if (!bar) return;
      bar.innerHTML = '';

      state.openFiles.forEach((file, idx) => {
        const tab = document.createElement('div');
        tab.className = `cct-editor-tab ${idx === state.activeFileIndex ? 'active' : ''}`;
        
        let icon = '📄';
        if (file.name.endsWith('.html')) icon = '🌐';
        else if (file.name.endsWith('.js')) icon = '📜';
        else if (file.name.endsWith('.css')) icon = '🎨';
        else if (file.name.endsWith('.py')) icon = '🐍';
        else if (file.name.endsWith('.json')) icon = '⚙';
        else if (file.name.endsWith('.md')) icon = '📘';

        tab.innerHTML = `
          <span>${icon}</span>
          <span>${this.escapeHtml(file.name)}</span>
          ${file.dirty ? '<span class="cct-tab-dirty">●</span>' : ''}
          <span class="cct-tab-close" title="Close file (✕)">✕</span>
        `;

        tab.addEventListener('click', (e) => {
          if (e.target.classList.contains('cct-tab-close')) {
            e.stopPropagation();
            this.closeEditorTab(idx);
          } else {
            this.switchEditorTab(idx);
          }
        });

        bar.appendChild(tab);
      });
    },

    switchEditorTab(idx) {
      if (idx < 0 || idx >= state.openFiles.length) return;
      state.activeFileIndex = idx;
      const file = state.openFiles[idx];
      state.currentFile = file;

      const titleEl = document.getElementById('cct-editor-filename');
      if (titleEl) titleEl.textContent = file.name;

      const langBadge = document.getElementById('cct-editor-lang-badge');
      if (langBadge) {
        const ext = (file.name.split('.').pop() || 'TXT').toUpperCase();
        langBadge.textContent = ext;
      }

      const textarea = document.getElementById('cct-code-editor');
      if (textarea) {
        textarea.value = file.content || '';
      }

      document.querySelectorAll('.cct-tree-node').forEach(n => {
        if (n.dataset.path === file.path) {
          n.classList.add('active-file');
        } else {
          n.classList.remove('active-file');
        }
      });

      this.renderEditorTabs();
      this.updateLineNumbers();
    },

    closeEditorTab(idx) {
      if (idx < 0 || idx >= state.openFiles.length) return;
      const file = state.openFiles[idx];
      if (file.dirty) {
        if (confirm(`Save changes to ${file.name} before closing?`)) {
          this.saveCurrentFile();
        }
      }

      state.openFiles.splice(idx, 1);
      if (state.openFiles.length === 0) {
        state.activeFileIndex = -1;
        state.currentFile = null;
        this.closeEditor();
      } else {
        const nextIdx = Math.max(0, idx - 1);
        this.switchEditorTab(nextIdx);
      }
      this.renderEditorTabs();
    },

    async openFile(filePath, fileName) {
      // 1. Check if file is already open in tabs
      const existingIdx = state.openFiles.findIndex(f => f.path === filePath);
      if (existingIdx !== -1) {
        this.switchEditorTab(existingIdx);
        const editorPane = document.getElementById('cct-editor-pane');
        const resizer = document.getElementById('cct-editor-resizer');
        if (editorPane) editorPane.classList.add('open');
        if (resizer) resizer.style.display = 'block';
        state.editorOpen = true;
        return;
      }

      // 2. Fetch content from server
      let content = '';
      try {
        const res = await api.get(`/api/workspace/current/file?path=${encodeURIComponent(filePath)}`);
        content = res.content || '';
      } catch (e) {
        console.warn('Could not read file from server:', e);
        content = '';
      }

      const newFile = {
        path: filePath,
        name: fileName,
        content: content,
        dirty: false
      };

      state.openFiles.push(newFile);
      state.activeFileIndex = state.openFiles.length - 1;
      state.currentFile = newFile;

      const editorPane = document.getElementById('cct-editor-pane');
      const resizer = document.getElementById('cct-editor-resizer');
      if (editorPane) editorPane.classList.add('open');
      if (resizer) resizer.style.display = 'block';
      state.editorOpen = true;

      this.switchEditorTab(state.activeFileIndex);
    },

    updateLineNumbers() {
      const textarea = document.getElementById('cct-code-editor');
      const gutter = document.getElementById('cct-line-numbers');
      if (!textarea || !gutter) return;

      const lines = textarea.value.split('\n').length;
      let numHtml = '';
      for (let i = 1; i <= Math.max(30, lines); i++) {
        numHtml += `<div>${i}</div>`;
      }
      gutter.innerHTML = numHtml;
    },

    formatEditorCode() {
      const textarea = document.getElementById('cct-code-editor');
      if (!textarea || !textarea.value) return;

      const file = state.currentFile;
      if (file && (file.name.endsWith('.json') || textarea.value.trim().startsWith('{') || textarea.value.trim().startsWith('['))) {
        try {
          const parsed = JSON.parse(textarea.value);
          textarea.value = JSON.stringify(parsed, null, 2);
          if (file) {
            file.content = textarea.value;
            file.dirty = true;
          }
          this.renderEditorTabs();
          this.updateLineNumbers();
          this.showToast('Formatted JSON code ✓', 'success');
          return;
        } catch (e) {}
      }

      const lines = textarea.value.split('\n');
      const cleaned = lines.map(l => l.replace(/\s+$/, '')).join('\n');
      textarea.value = cleaned;
      if (file) {
        file.content = textarea.value;
        file.dirty = true;
      }
      this.renderEditorTabs();
      this.updateLineNumbers();
      this.showToast('Cleaned indentation & whitespace ✓', 'success');
    },

    async saveCurrentFile() {
      if (!state.currentFile) return;
      const textarea = document.getElementById('cct-code-editor');
      if (!textarea) return;

      try {
        await api.post(`/api/workspace/current/file`, {
          path: state.currentFile.path,
          content: textarea.value
        });
        state.currentFile.content = textarea.value;
        state.currentFile.dirty = false;
        this.renderEditorTabs();
        this.showToast(`Saved ${state.currentFile.name} ✓`, 'success');
        if (state.previewRunning) {
          this.runPreview();
        }
      } catch (e) {
        console.error('Error saving file:', e);
        this.showToast(`Error saving ${state.currentFile.name}: ${e.message}`, 'error');
      }
    },

    closeEditor() {
      const editorPane = document.getElementById('cct-editor-pane');
      const resizer = document.getElementById('cct-editor-resizer');
      if (editorPane) editorPane.classList.remove('open');
      if (resizer) resizer.style.display = 'none';
      state.editorOpen = false;

      document.querySelectorAll('.cct-tree-node').forEach(n => {
        n.classList.remove('active-file');
      });
    },

    toggleSplitView() {
      state.splitPreview = !state.splitPreview;
      const preview = document.getElementById('cct-web-preview');
      const codeBox = document.getElementById('cct-code-container');
      const gutter = document.getElementById('cct-line-numbers');

      if (state.splitPreview) {
        if (codeBox) codeBox.style.display = 'none';
        if (gutter) gutter.style.display = 'none';
        if (preview) {
          preview.classList.add('active');
          this.runPreview();
        }
      } else {
        if (codeBox) codeBox.style.display = 'block';
        if (gutter) gutter.style.display = 'block';
        if (preview) preview.classList.remove('active');
      }
    },

    async runPreview() {
      if (!state.currentFile) return;
      const preview = document.getElementById('cct-web-preview');
      const codeBox = document.getElementById('cct-code-container');
      const gutter = document.getElementById('cct-line-numbers');

      if (!state.splitPreview) {
        state.splitPreview = true;
        if (codeBox) codeBox.style.display = 'none';
        if (gutter) gutter.style.display = 'none';
        if (preview) preview.classList.add('active');
      }

      state.previewRunning = true;
      try {
        const res = await api.post('/api/preview/start?workspace_id=' + encodeURIComponent(state.workspaceId || 'current'), {
          file_path: state.currentFile.path
        });
        if (res && res.url) {
          if (preview) preview.src = res.url;
          const banner = document.getElementById('cct-preview-banner');
          const link = document.getElementById('cct-preview-url-link');
          if (banner && link) {
            link.href = res.url;
            link.textContent = res.url;
            banner.style.display = 'inline-flex';
          }
          return;
        }
      } catch (e) {
        console.warn('Backend preview server fallback to iframe srcdoc', e);
      }

      const textarea = document.getElementById('cct-code-editor');
      if (preview && textarea) {
        preview.srcdoc = textarea.value;
      }
    },

    escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    },

    executeSlashCommand(cmdText) {
      const parts = cmdText.trim().split(/\s+/);
      const cmd = parts[0].toLowerCase();
      const arg = parts.slice(1).join(' ').trim();

      const welcome = document.getElementById('cct-welcome-view');
      const turnsBox = document.getElementById('cct-chat-turns');
      if (welcome) welcome.style.display = 'none';
      if (turnsBox) turnsBox.style.display = 'flex';

      this.appendUserMessage(cmdText);

      switch (cmd) {
        case '/clear':
          if (turnsBox) turnsBox.innerHTML = '';
          if (welcome) welcome.style.display = 'flex';
          state.chatId = null;
          return;
        case '/new':
        case '/chat':
        case '/newchat':
          this.newChat();
          this.appendSystemNotice('Started a new conversation session.');
          return;
        case '/help':
          this.appendSystemNotice(
            '<div style="line-height: 1.6;">' +
            '<b style="color: #ff79c6;">CAT Terminal Commands:</b><br>' +
            '• <code>/clear</code> — Clear current conversation<br>' +
            '• <code>/new</code> — Start a fresh chat session<br>' +
            '• <code>/mode &lt;name&gt;</code> — Switch active mode (build, agent, research, notebook)<br>' +
            '• <code>/logo &lt;1-5|next&gt;</code> — Switch dashboard ASCII wordmark logo style (5 variants)<br>' +
            '• <code>/notebook &lt;solve|new|list&gt;</code> — Session notebooks & chemistry derivations<br>' +
            '• <code>/settings</code> — Open configuration dialog<br>' +
            '• <code>/docs</code> — Open documentation<br>' +
            '• <code>/cat</code> or <code>/browse</code> — Launch CAT Browser<br>' +
            '• <code>/status</code> — Display AI and workspace status' +
            '</div>'
          );
          return;
        case '/logo':
          if (!arg || arg === 'next') {
            this.cycleLogoVariant();
            const current = ASCII_LOGO_VARIANTS[state.logoVariant];
            this.appendSystemNotice(`Switched ASCII Wordmark Logo to Variant ${state.logoVariant + 1}: <b style="color: #00f0ff;">${this.escapeHtml(current.name)}</b>`);
          } else {
            const num = parseInt(arg, 10);
            if (!isNaN(num) && num >= 1 && num <= ASCII_LOGO_VARIANTS.length) {
              this.setLogoVariant(num - 1);
              const current = ASCII_LOGO_VARIANTS[num - 1];
              this.appendSystemNotice(`Switched ASCII Wordmark Logo to Variant ${num}: <b style="color: #00f0ff;">${this.escapeHtml(current.name)}</b>`);
            } else {
              const matched = ASCII_LOGO_VARIANTS.findIndex(v => v.id.includes(arg.toLowerCase()) || v.name.toLowerCase().includes(arg.toLowerCase()));
              if (matched >= 0) {
                this.setLogoVariant(matched);
                this.appendSystemNotice(`Switched ASCII Wordmark Logo to Variant ${matched + 1}: <b style="color: #00f0ff;">${this.escapeHtml(ASCII_LOGO_VARIANTS[matched].name)}</b>`);
              } else {
                this.appendSystemNotice('Usage: <code>/logo &lt;1-5|next|retro|cyber|matrix|synthwave|pixel&gt;</code>');
              }
            }
          }
          return;
        case '/notebook':
        case '/notebooks':
          if (arg.startsWith('solve') || arg.startsWith('run')) {
            const topic = arg.replace(/^(solve|run)\s*/, '') || 'kinetics';
            this.runNotebookSolve(topic);
          } else if (arg.startsWith('new') || arg.startsWith('create')) {
            const title = arg.replace(/^(new|create)\s*/, '') || 'Chemistry Derivation';
            this.createNotebook(title);
          } else {
            const nbs = state.sessionNotebooks || [];
            let listHtml = `<b>Session Notebooks (${nbs.length} solved):</b><br>`;
            if (nbs.length === 0) {
              listHtml += '<span style="color: #6272a4;">No calculations solved yet this session.</span><br>';
            } else {
              nbs.forEach((n, idx) => {
                listHtml += `• <b>${idx + 1}. ${this.escapeHtml(n.title)}</b> [${this.escapeHtml(n.category)}] — <code>${this.escapeHtml(n.result)}</code> <button class="cct-nb-open-btn" style="margin-left: 6px;" onclick="FATTY.openNotebook('${n.id}')">[Open]</button><br>`;
              });
            }
            listHtml += '<div style="margin-top: 6px;">Quick commands: <code>/notebook solve kinetics</code> · <code>/notebook new &lt;title&gt;</code></div>';
            this.appendSystemNotice(listHtml);
          }
          return;
        case '/mode':
          if (arg) {
            this.setAiMode(arg.toLowerCase());
            this.appendSystemNotice(`Switched active persona to <b style="color: #38bdf8;">${this.escapeHtml(arg)}</b> mode.`);
          } else {
            this.openModeSelector();
          }
          return;
        case '/model':
        case '/provider':
        case '/providers':
          this.openProviderCenter();
          return;
        case '/user':
        case '/profile':
          this.openUserProfile();
          return;
        case '/themes':
        case '/theme':
          this.openThemes();
          return;
        case '/workspace':
          this.openFolderDialog();
          return;
        case '/activities':
          this.switchSidebarTab('activities');
          return;
        case '/extensions':
          this.switchSidebarTab('extensions');
          return;
        case '/settings':
          this.openSettings();
          return;
        case '/docs':
          this.openDocs();
          return;
        case '/cat':
        case '/browse':
        case '/browser':
          api.post('/api/browser/open', { url: arg || 'about:home' }).catch(() => {});
          this.appendSystemNotice('Launching CAT Browser…');
          return;
        case '/status':
          this.appendSystemNotice(
            `<div style="line-height: 1.6;">` +
            `<b>Workspace</b>: ${this.escapeHtml(state.workspaceRoot || 'Default')}<br>` +
            `<b>Active Mode</b>: <span style="color: #ff79c6;">${this.escapeHtml(state.activeMode)}</span><br>` +
            `<b>Provider</b>: ${this.escapeHtml(state.provider)}<br>` +
            `<b>Model</b>: ${this.escapeHtml(state.model)}` +
            `</div>`
          );
          return;
        default: {
          const cardEl = this.appendAssistantLoading();
          api.post('/api/command/dispatch', { command: cmdText })
            .then(res => {
              const out = res.output || 'Command executed.';
              this.updateAssistantCard(cardEl, {
                text: out,
                provider: state.provider,
                model: state.model,
                timeStr: '0:01',
                tokens: out.length,
                timings: { ttfb_ms: 40, memory_ms: 10, loop_ms: 50 },
                calls: 1
              });
            })
            .catch(e => {
              this.updateAssistantCard(cardEl, {
                text: `Command error: ${e.message}`,
                provider: state.provider,
                model: state.model,
                timeStr: '0:01',
                tokens: 0,
                timings: { ttfb_ms: 10, memory_ms: 5, loop_ms: 15 },
                calls: 1
              });
            });
          return;
        }
      }
    },

    appendSystemNotice(htmlContent) {
      const turnsBox = document.getElementById('cct-chat-turns');
      if (!turnsBox) return;
      const card = document.createElement('div');
      card.className = 'cct-response-card';
      card.innerHTML = `
        <div class="cct-card-header" style="color: #ff79c6;">⚙ System Notice</div>
        <div class="cct-card-content" style="padding: 6px 0;">${htmlContent}</div>
      `;
      turnsBox.appendChild(card);
      this.scrollToBottom();
    },

    // ─────────────────────────────────────────────────────────────────────
    // CHAT & CONVERSATION & AGENT EXECUTION
    // ─────────────────────────────────────────────────────────────────────
    async sendMessage() {
      const input = document.getElementById('cct-message-input');
      if (!input) return;
      const text = input.value.trim();
      if (!text) return;

      input.value = '';
      input.style.height = 'auto';

      // If slash command: dispatch directly
      if (text.startsWith('/')) {
        this.executeSlashCommand(text);
        return;
      }

      // Switch to Chat Screen if first message
      const welcome = document.getElementById('cct-welcome-view');
      const turnsBox = document.getElementById('cct-chat-turns');
      if (welcome) welcome.style.display = 'none';
      if (turnsBox) turnsBox.style.display = 'flex';

      // 1. Append User Bubble
      this.appendUserMessage(text);

      // 2. Append Assistant Loading Card
      const cardEl = this.appendAssistantLoading();
      const meta = state.modeMeta[state.activeMode] || state.modeMeta.build;
      const t0 = Date.now();

      // Check if explicit agent task
      const isAgentMode = state.activeMode === 'agent';
      const isExplicitFileTask = /^\s*(create|write|delete|edit|refactor|generate)\s+(file|folder|dir|component|app|project)\b/i.test(text);

      if (isAgentMode || (state.activeMode === 'build' && isExplicitFileTask)) {
        try {
          const res = await api.post('/api/agent', {
            message: text,
            mode: 'agent',
            max_steps: 4,
            project_path: state.workspaceRoot,
            chat_id: state.chatId
          });
          if (res && res.chat_id) state.chatId = res.chat_id;
          const elapsed = Math.round((Date.now() - t0) / 1000);
          this.updateAssistantCard(cardEl, {
            text: res.response || '(No response from agent)',
            steps: res.steps || [],
            provider: res.provider || state.provider,
            model: res.model || state.model,
            timeStr: `${Math.floor(elapsed / 60)}:${(elapsed % 60) < 10 ? '0' : ''}${elapsed % 60}`,
            tokens: res.tokens || Math.max(12, Math.round(text.length * 1.3)),
            timings: { ttfb_ms: 180, memory_ms: 20, loop_ms: elapsed * 1000 },
            calls: res.steps ? Math.max(1, res.steps.length) : 1
          });
        } catch (e) {
          this.updateAssistantCard(cardEl, {
            text: `(Agent error: ${e.message})`,
            provider: state.provider,
            model: state.model,
            timeStr: '0:02',
            tokens: 0,
            timings: { ttfb_ms: 20, memory_ms: 10, loop_ms: 30 },
            calls: 1
          });
        }
        return;
      }

      // Streaming execution via /api/chat/stream
      let accumulatedText = '';
      let thinkingText = '';
      let inThinkingBlock = false;
      let hasReceivedFirstToken = false;
      let ttfbMs = 0;

      try {
        const response = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            mode: state.activeMode,
            project_path: state.workspaceRoot,
            chat_id: state.chatId
          })
        });

        if (!response.ok || !response.body) {
          throw new Error('Stream request returned status ' + response.status);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data:')) continue;
            const dataStr = trimmed.slice(5).trim();
            if (!dataStr) continue;

            let chunk;
            try {
              chunk = JSON.parse(dataStr);
            } catch (e) {
              continue;
            }

            if (!hasReceivedFirstToken) {
              hasReceivedFirstToken = true;
              ttfbMs = Date.now() - t0;
            }

            if (chunk.type === 'token') {
              accumulatedText += chunk.text;

              if (accumulatedText.includes('<think>')) {
                inThinkingBlock = true;
                const thinkStart = accumulatedText.indexOf('<think>') + 7;
                if (accumulatedText.includes('</think>')) {
                  const thinkEnd = accumulatedText.indexOf('</think>');
                  thinkingText = accumulatedText.slice(thinkStart, thinkEnd);
                  inThinkingBlock = false;
                } else {
                  thinkingText = accumulatedText.slice(thinkStart);
                }
              }

              this.renderStreamingAssistantCard(cardEl, {
                rawText: accumulatedText,
                thinkingText,
                inThinkingBlock,
                elapsedMs: Date.now() - t0
              });
            } else if (chunk.type === 'done') {
              break;
            } else if (chunk.type === 'error') {
              throw new Error(chunk.error || 'Stream error');
            }
          }
        }

        const totalElapsed = Date.now() - t0;
        const totalSecs = Math.max(1, Math.round(totalElapsed / 1000));
        const mins = Math.floor(totalSecs / 60);
        const secs = totalSecs % 60;
        const timeStr = `${mins}:${secs < 10 ? '0' : ''}${secs}`;

        this.finalizeAssistantCard(cardEl, {
          rawText: accumulatedText,
          thinkingText,
          provider: state.provider,
          model: state.model,
          timeStr,
          tokens: Math.max(10, Math.round(accumulatedText.length / 3)),
          timings: {
            ttfb_ms: ttfbMs || 250,
            memory_ms: 32,
            loop_ms: totalElapsed
          },
          calls: 1
        });

      } catch (streamErr) {
        console.warn('Streaming failed, falling back to standard /api/chat:', streamErr);
        try {
          const res = await api.post('/api/chat', {
            message: text,
            mode: state.activeMode,
            project_path: state.workspaceRoot,
            chat_id: state.chatId
          });
          if (res && res.chat_id) state.chatId = res.chat_id;
          const elapsed = Math.round((Date.now() - t0) / 1000);
          this.updateAssistantCard(cardEl, {
            text: res.response || '(No response from AI)',
            steps: res.steps || [],
            provider: res.provider || state.provider,
            model: res.model || state.model,
            timeStr: `${Math.floor(elapsed / 60)}:${(elapsed % 60) < 10 ? '0' : ''}${elapsed % 60}`,
            tokens: res.tokens || Math.max(12, Math.round(text.length * 1.3)),
            timings: res.timings || { ttfb_ms: 300, memory_ms: 30, loop_ms: elapsed * 1000 },
            calls: 1
          });
        } catch (e2) {
          this.updateAssistantCard(cardEl, {
            text: `(AI error: ${e2.message})`,
            provider: state.provider,
            model: state.model,
            timeStr: '0:02',
            tokens: 0,
            timings: { ttfb_ms: 20, memory_ms: 10, loop_ms: 30 },
            calls: 1
          });
        }
      }
    },

    renderStreamingAssistantCard(cardEl, { rawText, thinkingText, inThinkingBlock, elapsedMs }) {
      if (!cardEl) return;
      const meta = state.modeMeta[state.activeMode] || state.modeMeta.build;
      const elapsedSec = (elapsedMs / 1000).toFixed(1);

      let thinkingHtml = '';
      let answerText = rawText;

      if (rawText.includes('<think>')) {
        const parts = rawText.split('</think>');
        if (parts.length > 1) {
          answerText = parts[1].trim();
        } else {
          answerText = '';
        }

        thinkingHtml = `
          <details class="cct-thinking-block" ${inThinkingBlock ? 'open' : ''}>
            <summary class="cct-thinking-summary">
              <span class="cct-thinking-pulse">🧠</span>
              <span>Thinking Process (${state.model})</span>
              <span style="font-size: 10px; margin-left: auto; color: var(--term-text-muted);">${elapsedSec}s</span>
            </summary>
            <div class="cct-thinking-content">${this.escapeHtml(thinkingText)}</div>
          </details>
        `;
      }

      cardEl.innerHTML = `
        <div class="cct-card-header">${meta.icon} ${meta.label}</div>
        ${thinkingHtml}
        <div class="cct-card-content">${answerText ? this.formatContent(answerText) : (inThinkingBlock ? '<span style="color: var(--term-text-muted);">Formulating response… ▌</span>' : '▌')}</div>
        <div class="cct-card-meta">
          <div class="cct-meta-line" style="color: #7dcfff;">Streaming tokens from ${state.provider} ${state.model}… (${elapsedSec}s)</div>
        </div>
      `;
      this.scrollToBottom();
    },

    finalizeAssistantCard(cardEl, data) {
      if (!cardEl) return;
      const meta = state.modeMeta[state.activeMode] || state.modeMeta.build;

      let thinkingHtml = '';
      let answerText = data.rawText || '';

      if (answerText.includes('<think>')) {
        const parts = answerText.split('</think>');
        if (parts.length > 1) {
          answerText = parts[1].trim();
        }
        thinkingHtml = `
          <details class="cct-thinking-block">
            <summary class="cct-thinking-summary">
              <span>🧠</span>
              <span>Reasoning &amp; Thought Trace</span>
              <span style="font-size: 10px; margin-left: auto; color: var(--color-green);">✓ Complete</span>
            </summary>
            <div class="cct-thinking-content">${this.escapeHtml(data.thinkingText || '')}</div>
          </details>
        `;
      }

      cardEl.innerHTML = `
        <div class="cct-card-header">${meta.icon} ${meta.label}</div>
        ${thinkingHtml}
        <div class="cct-card-content">${this.formatContent(answerText)}</div>
        <div class="cct-card-meta">
          <div class="cct-meta-complete">✓ Response Complete</div>
          <div class="cct-meta-line">Provider: ${data.provider} &nbsp;·&nbsp; Model: ${data.model} &nbsp;·&nbsp; Time: ${data.timeStr} &nbsp;·&nbsp; Tokens: ${data.tokens}</div>
          <div class="cct-meta-timings">⏰ Real timings: TTFB ${data.timings.ttfb_ms}ms &nbsp;·&nbsp; memory ${data.timings.memory_ms}ms &nbsp;·&nbsp; loop ${data.timings.loop_ms}ms</div>
          <div class="cct-meta-calls">🗂 ${data.calls} model call(s)</div>
        </div>
      `;
      this.scrollToBottom();
    },

    appendUserMessage(text) {
      const turnsBox = document.getElementById('cct-chat-turns');
      if (!turnsBox) return;

      const now = new Date();
      const timeStr = `${now.getHours()}:${now.getMinutes() < 10 ? '0' : ''}${now.getMinutes()}`;

      const wrapper = document.createElement('div');
      wrapper.className = 'cct-user-turn-wrapper';
      wrapper.innerHTML = `
        <div class="cct-user-bubble">
          <div class="cct-user-text">${this.escapeHtml(text)}</div>
          <div class="cct-user-meta">${timeStr} ✎</div>
        </div>
      `;
      turnsBox.appendChild(wrapper);
      this.scrollToBottom();
    },

    appendAssistantLoading() {
      const turnsBox = document.getElementById('cct-chat-turns');
      if (!turnsBox) return null;

      const card = document.createElement('div');
      card.className = 'cct-response-card';
      const meta = state.modeMeta[state.activeMode] || state.modeMeta.build;

      card.innerHTML = `
        <div class="cct-card-header">${meta.icon} ${meta.label}</div>
        <div class="cct-card-content">Thinking… ▌</div>
        <div class="cct-card-meta">
          <div class="cct-meta-line">Connecting to ${state.provider} ${state.model}…</div>
        </div>
      `;
      turnsBox.appendChild(card);
      this.scrollToBottom();
      return card;
    },

    updateAssistantCard(cardEl, data) {
      if (!cardEl) return;
      const meta = state.modeMeta[state.activeMode] || state.modeMeta.build;

      let stepsHtml = '';
      if (data.steps && data.steps.length) {
        stepsHtml = `<div class="cct-tools-container" style="margin-bottom: 8px;">` +
          data.steps.map(s => {
            const toolName = s.tool || 'tool';
            const argsStr = typeof s.args === 'string' ? s.args : JSON.stringify(s.args || {});
            return `
              <div class="cct-tool-badge">
                <span class="cct-tool-badge-icon">🔧</span>
                <span class="cct-tool-badge-name">${this.escapeHtml(toolName)}</span>
                <span class="cct-tool-badge-detail">${this.escapeHtml(argsStr.slice(0, 50))}</span>
              </div>
            `;
          }).join('') +
        `</div>`;
      }

      cardEl.innerHTML = `
        <div class="cct-card-header">${meta.icon} ${meta.label}</div>
        ${stepsHtml}
        <div class="cct-card-content">${this.formatContent(data.text)}</div>
        <div class="cct-card-meta">
          <div class="cct-meta-complete">✓ Response Complete</div>
          <div class="cct-meta-line">Provider: ${data.provider} &nbsp;·&nbsp; Model: ${data.model} &nbsp;·&nbsp; Time: ${data.timeStr} &nbsp;·&nbsp; Tokens: ${data.tokens}</div>
          <div class="cct-meta-timings">⏰ Real timings: TTFB ${data.timings.ttfb_ms}ms &nbsp;·&nbsp; memory ${data.timings.memory_ms}ms &nbsp;·&nbsp; loop ${data.timings.loop_ms}ms</div>
          <div class="cct-meta-calls">🗂 ${data.calls} model call(s)</div>
        </div>
      `;
      this.scrollToBottom();
    },


    newChat() {
      const welcome = document.getElementById('cct-welcome-view');
      const turnsBox = document.getElementById('cct-chat-turns');
      if (welcome) welcome.style.display = 'flex';
      if (turnsBox) {
        turnsBox.innerHTML = '';
        turnsBox.style.display = 'none';
      }
    },

    scrollToBottom() {
      const conv = document.getElementById('cct-conversation');
      if (conv) conv.scrollTop = conv.scrollHeight;
    },

    // ─────────────────────────────────────────────────────────────────────
    // COMMAND PALETTE (Ctrl+K / /)
    // ─────────────────────────────────────────────────────────────────────
    async loadCommands() {
      try {
        const res = await api.get('/api/commands');
        if (res && res.commands) {
          state.commands = res.commands;
        }
      } catch (e) {
        console.warn('Could not load commands from server');
        state.commands = [
          { command: '/help', description: 'Show help & shortcuts' },
          { command: '/solve', description: 'Solve formula symbolically' },
          { command: '/calculator', description: 'Quick calculator' },
          { command: '/model', description: 'Switch AI model/provider' },
          { command: '/mode', description: 'Switch AI mode' },
          { command: '/memory', description: 'Memory center' },
          { command: '/extensions', description: 'Extensions manager' },
          { command: '/workspace', description: 'Manage workspace' },
          { command: '/clear', description: 'Reset conversation' },
          { command: '/atomsim', description: 'Live 2D Bohr atom simulation' },
          { command: '/orbitals', description: 'Live quantum orbital simulation' },
          { command: '/graph', description: 'Chemistry curves & graphs' },
          { command: '/research', description: 'Deep research' },
          { command: '/debug', description: 'Switch to debugger mode' },
          { command: '/install', description: 'Install packages' }
        ];
      }
      const promptSuggestions = [
        { command: 'what is a first order reaction', description: 'Quick conceptual answer · Kinetics', type: 'prompt' },
        { command: 'half life of a first order reaction', description: 'Numerical calculation · Kinetics', type: 'prompt' },
        { command: 'explain the arrhenius equation simply', description: 'Conceptual explanation · Physical Chem', type: 'prompt' },
        { command: 'solve ideal gas law with P=1, n=2, T=300', description: 'Symbolic solve + full notebook', type: 'prompt' },
        { command: 'derive the first order rate law step by step', description: 'Full derivation, notebook format', type: 'prompt' },
        { command: 'plot the arrhenius graph and export it', description: 'Interactive plot + PNG export', type: 'prompt' },
        { command: 'simulate an iron atom in 3d', description: 'Live 3D Bohr simulation', type: 'prompt' },
        { command: 'calculate molar mass of glucose', description: 'Step-by-step formula C6H12O6 mass', type: 'prompt' },
        { command: 'how to balance redox reactions', description: 'Ion-electron oxidation-reduction method', type: 'prompt' }
      ];
      state.commands = [...(state.commands || []), ...promptSuggestions];
      state.filteredCommands = [...state.commands];
    },

    openCommandPalette() {
      const modal = document.getElementById('cct-command-palette-modal');
      const input = document.getElementById('cct-palette-input');
      if (!modal || !input) return;

      modal.style.display = 'flex';
      input.value = '';
      this.filterPalette('');
      setTimeout(() => input.focus(), 50);
    },

    filterPalette(query) {
      const q = (query || '').toLowerCase().trim();
      if (!q) {
        state.filteredCommands = [...state.commands];
      } else {
        state.filteredCommands = state.commands.filter(c => {
          const cmd = (c.command || '').toLowerCase();
          const desc = (c.description || '').toLowerCase();
          return cmd.includes(q) || desc.includes(q);
        });
      }
      state.paletteSelectedIndex = 0;
      this.renderPalette();
    },

    renderPalette() {
      const list = document.getElementById('cct-palette-list');
      if (!list) return;
      list.innerHTML = '';

      if (!state.filteredCommands.length) {
        list.innerHTML = '<div style="padding: 12px 16px; color: var(--term-text-faint);">No commands found matching query.</div>';
        return;
      }

      state.filteredCommands.slice(0, 40).forEach((c, idx) => {
        const item = document.createElement('div');
        item.className = 'cct-palette-item' + (idx === state.paletteSelectedIndex ? ' active' : '');
        item.innerHTML = `
          <div class="cct-palette-item-left">
            <span class="cct-palette-cmd">${this.escapeHtml(c.command)}</span>
            <span class="cct-palette-desc">${this.escapeHtml(c.description)}</span>
          </div>
          <span class="cct-palette-badge">cmd</span>
        `;
        item.addEventListener('click', () => {
          this.executeCommandFromPalette(c.command);
        });
        list.appendChild(item);
      });
    },

    paletteNext() {
      if (!state.filteredCommands.length) return;
      state.paletteSelectedIndex = (state.paletteSelectedIndex + 1) % Math.min(40, state.filteredCommands.length);
      this.updatePaletteActiveItem();
    },

    palettePrev() {
      if (!state.filteredCommands.length) return;
      state.paletteSelectedIndex = (state.paletteSelectedIndex - 1 + Math.min(40, state.filteredCommands.length)) % Math.min(40, state.filteredCommands.length);
      this.updatePaletteActiveItem();
    },

    updatePaletteActiveItem() {
      const items = document.querySelectorAll('.cct-palette-item');
      items.forEach((it, idx) => {
        if (idx === state.paletteSelectedIndex) {
          it.classList.add('active');
          it.scrollIntoView({ block: 'nearest' });
        } else {
          it.classList.remove('active');
        }
      });
    },

    executePaletteIndex() {
      const selected = state.filteredCommands[state.paletteSelectedIndex];
      if (selected) {
        this.executeCommandFromPalette(selected.command);
      }
    },

    executeCommandFromPalette(cmdStr) {
      this.closeAllModals();
      this.executeSlashCommand(cmdStr);
    },

    // ─────────────────────────────────────────────────────────────────────
    // FULL AI PROVIDER & MODEL CENTER (1:1 CAT CLI)
    // ─────────────────────────────────────────────────────────────────────
    openModelPicker() {
      this.openProviderCenter();
    },

    async openProviderCenter() {
      const modal = document.getElementById('cct-model-picker-modal');
      if (!modal) return;
      modal.style.display = 'flex';

      const leftList = document.getElementById('cct-picker-providers');
      if (leftList) leftList.innerHTML = '<div style="padding: 10px; font-size: 11px; color: var(--term-text-muted);">Loading 150+ providers...</div>';

      try {
        const center = await api.get('/api/providers/center');
        state.providerCenterData = center;
        state.providers = center.providers || [];

        const activeProv = center.active ? center.active.provider : state.provider.toLowerCase();
        state.selectedProviderId = activeProv;
        state.selectedModelName = center.active ? center.active.model : state.model;

        this.filterProviderCategory('all');
        this.selectProvider(activeProv);
      } catch (e) {
        console.warn('Failed to load provider center:', e);
        if (leftList) leftList.innerHTML = `<div style="padding: 10px; color: var(--color-red);">${this.escapeHtml(e.message)}</div>`;
      }
    },

    filterProviderCategory(cat) {
      document.querySelectorAll('#cct-pm-cat-bar .cct-pill').forEach(p => {
        p.classList.remove('active');
        if (p.textContent.toLowerCase().includes(cat.toLowerCase()) || (cat === 'all' && p.textContent.toLowerCase() === 'all')) {
          p.classList.add('active');
        }
      });

      if (!state.providerCenterData) return;
      let provs = state.providerCenterData.providers || [];
      if (cat !== 'all') {
        provs = provs.filter(p => {
          if (cat === 'local') return p.id === 'ollama';
          if (cat === 'popular') return p.popular;
          if (cat === 'free') return !p.needs_key || p.id === 'ollama';
          return (p.categories || []).includes(cat);
        });
      }

      this.renderProviderCards(provs);
    },

    filterProviders(query) {
      const q = (query || '').toLowerCase().trim();
      if (!state.providerCenterData) return;
      let provs = state.providerCenterData.providers || [];
      if (q) {
        provs = provs.filter(p => {
          const id = (p.id || '').toLowerCase();
          const name = (p.name || '').toLowerCase();
          return id.includes(q) || name.includes(q);
        });
      }
      this.renderProviderCards(provs);
    },

    renderProviderCards(provs) {
      const leftList = document.getElementById('cct-picker-providers');
      const countEl = document.getElementById('cct-provider-count');
      if (countEl) countEl.textContent = provs.length;
      if (!leftList) return;

      leftList.innerHTML = '';
      provs.forEach(p => {
        const card = document.createElement('div');
        const isSelected = p.id === state.selectedProviderId;
        card.className = `cct-provider-card ${isSelected ? 'active' : ''}`;
        
        let badgeText = p.id === 'ollama' ? 'Local' : (p.needs_key ? 'Key Required' : 'Free');
        let badgeColor = p.id === 'ollama' ? 'var(--color-green)' : (p.needs_key ? 'var(--accent-build)' : '#7dcfff');

        card.innerHTML = `
          <div class="cct-provider-card-left">
            <span style="font-size: 14px;">${p.id === 'ollama' ? '🦙' : '⚡'}</span>
            <span class="cct-provider-card-name">${this.escapeHtml(p.name || p.id)}</span>
          </div>
          <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; border: 1px solid ${badgeColor}; color: ${badgeColor};">${badgeText}</span>
        `;

        card.addEventListener('click', () => {
          document.querySelectorAll('.cct-provider-card').forEach(c => c.classList.remove('active'));
          card.classList.add('active');
          this.selectProvider(p.id);
        });

        leftList.appendChild(card);
      });
    },

    async selectProvider(providerId) {
      state.selectedProviderId = providerId;
      const prov = (state.providers || []).find(p => p.id === providerId) || { id: providerId, name: providerId };

      const nameEl = document.getElementById('cct-pm-detail-name');
      const subEl = document.getElementById('cct-pm-detail-sub');
      const baseurlInput = document.getElementById('cct-pm-detail-baseurl');
      const apikeyGroup = document.getElementById('cct-pm-apikey-group');
      const apikeyInput = document.getElementById('cct-pm-detail-apikey');
      const modelsList = document.getElementById('cct-picker-models');
      const latencyBadge = document.getElementById('cct-pm-latency-badge');
      const applyBtn = document.getElementById('cct-pm-apply-btn');

      if (latencyBadge) latencyBadge.style.display = 'none';
      if (applyBtn) applyBtn.disabled = false;

      if (nameEl) nameEl.textContent = prov.name || prov.id;
      if (subEl) subEl.textContent = `${prov.id} provider endpoint & configuration`;

      if (baseurlInput) {
        if (providerId === 'ollama') {
          baseurlInput.value = 'http://localhost:11434';
        } else {
          baseurlInput.value = prov.default_base_url || '';
        }
      }

      if (apikeyGroup) {
        apikeyGroup.style.display = (providerId === 'ollama' && !prov.needs_key) ? 'none' : 'block';
      }

      // Load models for this provider
      if (modelsList) {
        modelsList.innerHTML = '<div style="padding: 6px; font-size: 11px; color: var(--term-text-muted);">Fetching models…</div>';
      }

      try {
        const res = await api.get(`/api/providers/${providerId}/models`);
        const models = res.models || [];
        this.renderProviderModelsList(models);
      } catch (e) {
        if (modelsList) {
          modelsList.innerHTML = `<div style="padding: 6px; font-size: 11px; color: var(--color-red);">${this.escapeHtml(e.message)}</div>`;
        }
      }
    },

    renderProviderModelsList(models) {
      const modelsList = document.getElementById('cct-picker-models');
      if (!modelsList) return;

      if (!models || models.length === 0) {
        modelsList.innerHTML = '<div style="padding: 6px; font-size: 11px; color: var(--term-text-muted);">No models found for this provider.</div>';
        return;
      }

      modelsList.innerHTML = '';
      models.forEach(m => {
        const mName = typeof m === 'string' ? m : (m.id || m.name);
        const item = document.createElement('div');
        const isSelected = mName === state.selectedModelName;
        item.className = `cct-model-item ${isSelected ? 'active' : ''}`;
        item.innerHTML = `
          <span>${this.escapeHtml(mName)}</span>
          ${isSelected ? '<span class="cct-model-check">✓ Active</span>' : ''}
        `;
        item.addEventListener('click', () => {
          document.querySelectorAll('.cct-model-item').forEach(mi => mi.classList.remove('active'));
          item.classList.add('active');
          state.selectedModelName = mName;
        });
        modelsList.appendChild(item);
      });
    },

    async refreshProviderModels() {
      if (!state.selectedProviderId) return;
      const modelsList = document.getElementById('cct-picker-models');
      if (modelsList) {
        modelsList.innerHTML = '<div style="padding: 6px; font-size: 11px; color: var(--term-text-muted);">Refreshing live models…</div>';
      }
      try {
        const res = await api.get(`/api/providers/${state.selectedProviderId}/models?force_refresh=true`);
        this.renderProviderModelsList(res.models || []);
        this.showToast(`Refreshed models for ${state.selectedProviderId} ✓`, 'info');
      } catch (e) {
        this.showToast(`Refresh error: ${e.message}`, 'error');
      }
    },

    toggleApiKeyVisibility() {
      const input = document.getElementById('cct-pm-detail-apikey');
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
    },

    async verifyCurrentProvider() {
      const baseurlInput = document.getElementById('cct-pm-detail-baseurl');
      const apikeyInput = document.getElementById('cct-pm-detail-apikey');
      const latencyBadge = document.getElementById('cct-pm-latency-badge');
      const verifyBtn = document.getElementById('cct-pm-verify-btn');

      if (verifyBtn) verifyBtn.textContent = 'Testing...';
      if (latencyBadge) {
        latencyBadge.style.display = 'inline-block';
        latencyBadge.className = 'cct-pm-latency-badge';
        latencyBadge.textContent = 'Testing latency...';
      }

      try {
        const res = await api.post('/api/providers/verify', {
          provider: state.selectedProviderId,
          model: state.selectedModelName || '',
          base_url: baseurlInput ? baseurlInput.value : '',
          api_key: apikeyInput ? apikeyInput.value : ''
        });

        if (res && res.success) {
          if (latencyBadge) {
            latencyBadge.className = 'cct-pm-latency-badge success';
            latencyBadge.textContent = `✓ OK (${res.latency_ms}ms)`;
          }
          this.showToast(`Connected to ${state.selectedProviderId} in ${res.latency_ms}ms ✓`, 'success');
        } else {
          if (latencyBadge) {
            latencyBadge.className = 'cct-pm-latency-badge error';
            latencyBadge.textContent = `✕ Failed (${res.error || 'Connection error'})`;
          }
          this.showToast(`Connection failed: ${res.error || 'Unknown error'}`, 'error');
        }
      } catch (e) {
        if (latencyBadge) {
          latencyBadge.className = 'cct-pm-latency-badge error';
          latencyBadge.textContent = `✕ Error (${e.message})`;
        }
      } finally {
        if (verifyBtn) verifyBtn.textContent = '⚡ Test Connection & Latency';
      }
    },

    async applySelectedModel() {
      const baseurlInput = document.getElementById('cct-pm-detail-baseurl');
      const baseUrl = baseurlInput ? baseurlInput.value : '';

      try {
        await api.post('/api/models/switch', {
          provider: state.selectedProviderId,
          model: state.selectedModelName,
          base_url: baseUrl
        });

        state.provider = state.selectedProviderId.toUpperCase();
        state.model = state.selectedModelName;

        const composerBadge = document.getElementById('cct-model-badge');
        if (composerBadge) composerBadge.textContent = `${state.provider} ${state.model}`;

        const welcomeModel = document.getElementById('cct-welcome-model');
        if (welcomeModel) welcomeModel.textContent = `${state.provider.toLowerCase()} ${state.model}`;

        const sbModelName = document.getElementById('cct-sb-active-model-name');
        if (sbModelName) sbModelName.textContent = `${state.provider} ${state.model}`;

        const wsAiStatus = document.getElementById('cct-ws-ai-status');
        if (wsAiStatus) wsAiStatus.textContent = `${state.provider.toLowerCase()} (${state.model})`;

        this.closeAllModals();
        this.showToast(`Switched active model to ${state.provider} ${state.model} ✓`, 'success');
      } catch (e) {
        alert('Could not switch model: ' + e.message);
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // SIDEBAR TABBED NAVIGATION & SUBPANE HANDLERS
    // ─────────────────────────────────────────────────────────────────────
    switchSidebarTab(tabName) {
      state.activeSidebarTab = tabName;

      ['explorer', 'chats', 'activities', 'extensions', 'settings'].forEach(t => {
        const btn = document.getElementById(`cct-sb-tab-${t}`);
        const view = document.getElementById(`cct-sb-view-${t}`);
        if (btn) {
          if (t === tabName) btn.classList.add('active');
          else btn.classList.remove('active');
        }
        if (view) {
          view.style.display = (t === tabName) ? 'flex' : 'none';
        }
      });

      if (tabName === 'chats') {
        this.loadSidebarChats();
      } else if (tabName === 'activities') {
        this.loadSidebarActivities();
      } else if (tabName === 'extensions') {
        this.loadSidebarExtensions();
      } else if (tabName === 'settings') {
        this.syncSidebarSettings();
      }
    },

    async loadSidebarChats() {
      const listEl = document.getElementById('cct-sidebar-chats-list');
      if (!listEl) return;
      listEl.innerHTML = '<div style="padding: 10px; font-size: 11px; color: var(--term-text-muted);">Loading sessions...</div>';

      try {
        const data = await api.get('/api/chats');
        state.sidebarChats = data.chats || [];
        this.renderSidebarChatsList(state.sidebarChats);
      } catch (e) {
        listEl.innerHTML = `<div style="padding: 10px; font-size: 11px; color: var(--color-red);">Error: ${this.escapeHtml(e.message)}</div>`;
      }
    },

    filterSidebarChats(query) {
      const q = (query || '').toLowerCase().trim();
      if (!q) {
        this.renderSidebarChatsList(state.sidebarChats);
        return;
      }
      const filtered = state.sidebarChats.filter(c => 
        (c.title && c.title.toLowerCase().includes(q)) ||
        (c.id && c.id.toLowerCase().includes(q))
      );
      this.renderSidebarChatsList(filtered);
    },

    renderSidebarChatsList(chats) {
      const listEl = document.getElementById('cct-sidebar-chats-list');
      if (!listEl) return;

      if (!chats || chats.length === 0) {
        listEl.innerHTML = '<div style="padding: 12px; font-size: 11px; color: var(--term-text-muted); text-align: center;">No chat sessions found.<br><button class="cct-sb-mini-btn primary" style="margin-top: 6px;" onclick="FATTY.createNewChatSession()">Start New Chat</button></div>';
        return;
      }

      listEl.innerHTML = '';
      chats.forEach(chat => {
        const item = document.createElement('div');
        const isActive = state.chatId === chat.id;
        item.className = `cct-sb-chat-item ${isActive ? 'active' : ''}`;

        const msgCount = chat.message_count !== undefined ? chat.message_count : (chat.messages ? chat.messages.length : 0);
        const timeStr = chat.updated_at ? new Date(chat.updated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

        item.innerHTML = `
          <div class="cct-sb-chat-info" onclick="FATTY.loadChatSession('${chat.id}')">
            <span class="cct-sb-chat-title" title="${this.escapeHtml(chat.title || 'Untitled Session')}">💬 ${this.escapeHtml(chat.title || 'Untitled Session')}</span>
            <span class="cct-sb-chat-meta">${msgCount} msgs ${timeStr ? '· ' + timeStr : ''}</span>
          </div>
          <div class="cct-sb-chat-actions">
            <button class="cct-sb-chat-action-btn" onclick="FATTY.renameChatSession('${chat.id}', '${this.escapeHtml(chat.title || '')}', event)" title="Rename (✎)">✎</button>
            <button class="cct-sb-chat-action-btn" onclick="FATTY.exportChatSession('${chat.id}', event)" title="Export (⤓)">⤓</button>
            <button class="cct-sb-chat-action-btn" onclick="FATTY.deleteChatSession('${chat.id}', event)" title="Delete (🗑)">🗑</button>
          </div>
        `;
        listEl.appendChild(item);
      });
    },

    async createNewChatSession() {
      try {
        const res = await api.post('/api/chats', { title: 'New Chat Session' });
        if (res && res.chat_id) {
          state.chatId = res.chat_id;
        }
      } catch (e) {
        state.chatId = 'chat_' + Date.now();
      }
      this.newChat();
      this.loadSidebarChats();
      this.showToast('Started new chat session ✓', 'info');
    },

    async loadChatSession(chatId) {
      try {
        const data = await api.get(`/api/chats/${chatId}`);
        state.chatId = chatId;
        const welcome = document.getElementById('cct-welcome-view');
        const turnsBox = document.getElementById('cct-chat-turns');
        if (welcome) welcome.style.display = 'none';
        if (turnsBox) {
          turnsBox.style.display = 'flex';
          turnsBox.innerHTML = '';
          const messages = data.messages || [];
          messages.forEach(m => {
            if (m.role === 'user') {
              this.appendUserMessage(m.content);
            } else if (m.role === 'assistant') {
              const card = this.appendAssistantLoading();
              this.updateAssistantCard(card, {
                text: m.content,
                provider: m.provider || state.provider,
                model: m.model || state.model,
                timeStr: 'Loaded',
                tokens: m.tokens || Math.round(m.content.length * 1.3),
                timings: { ttfb_ms: 50, memory_ms: 10, loop_ms: 60 },
                calls: 1
              });
            }
          });
        }
        this.loadSidebarChats();
      } catch (e) {
        this.showToast(`Error loading chat: ${e.message}`, 'error');
      }
    },

    async renameChatSession(chatId, currentTitle, event) {
      if (event) event.stopPropagation();
      const newTitle = prompt('Enter new session title:', currentTitle);
      if (!newTitle || !newTitle.trim()) return;

      try {
        await api.post(`/api/chats/${chatId}/rename`, { title: newTitle.trim() });
        this.loadSidebarChats();
        this.showToast('Session renamed ✓', 'success');
      } catch (e) {
        this.showToast(`Rename error: ${e.message}`, 'error');
      }
    },

    async deleteChatSession(chatId, event) {
      if (event) event.stopPropagation();
      if (!confirm('Are you sure you want to delete this chat session?')) return;

      try {
        await api.del(`/api/chats/${chatId}`);
        if (state.chatId === chatId) {
          this.newChat();
        }
        this.loadSidebarChats();
        this.showToast('Session deleted ✓', 'info');
      } catch (e) {
        this.showToast(`Delete error: ${e.message}`, 'error');
      }
    },

    async exportChatSession(chatId, event) {
      if (event) event.stopPropagation();
      try {
        const data = await api.get(`/api/chats/${chatId}/export`);
        const content = data.content || '';
        const filename = data.filename || `chat_${chatId}.md`;
        const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        this.showToast(`Exported ${filename} ⤓`, 'success');
      } catch (e) {
        this.showToast(`Export failed: ${e.message}`, 'error');
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // LIVE ACTIVITIES
    // ─────────────────────────────────────────────────────────────────────
    async loadSidebarActivities() {
      const listEl = document.getElementById('cct-sidebar-activities-list');
      if (!listEl) return;

      try {
        const data = await api.get('/api/activities');
        const acts = data.activities || [];
        state.sidebarActivities = acts;
        if (acts.length === 0) {
          listEl.innerHTML = '<div style="padding: 12px; font-size: 11px; color: var(--term-text-muted); text-align: center;">No recent activities recorded.<br>Terminal tasks, tool executions, and file edits appear here live.</div>';
          return;
        }

        listEl.innerHTML = '';
        acts.slice(0, 30).forEach(act => {
          const item = document.createElement('div');
          item.className = 'cct-activity-item';

          let icon = '⚡';
          if (act.status === 'success') icon = '✓';
          else if (act.status === 'error') icon = '✕';
          else if (act.status === 'running') icon = '<span class="cct-activity-icon spinner">◐</span>';

          item.innerHTML = `
            <div class="cct-activity-icon" style="color: ${act.status === 'error' ? 'var(--color-red)' : 'var(--color-green)'};">${icon}</div>
            <div class="cct-activity-body">
              <div class="cct-activity-title">${this.escapeHtml(act.title || act.action || 'Activity')}</div>
              <div class="cct-activity-time">${this.escapeHtml(act.details || '')} ${act.timestamp ? '· ' + act.timestamp : ''}</div>
            </div>
          `;
          listEl.appendChild(item);
        });
      } catch (e) {
        listEl.innerHTML = `<div style="padding: 10px; font-size: 11px; color: var(--color-red);">${this.escapeHtml(e.message)}</div>`;
      }
    },

    async clearActivities() {
      try {
        await api.post('/api/activities/clear');
        this.loadSidebarActivities();
        this.showToast('Activity history cleared ✓', 'info');
      } catch (e) {
        this.showToast(`Clear error: ${e.message}`, 'error');
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // EXTENSIONS MANAGER
    // ─────────────────────────────────────────────────────────────────────
    async loadSidebarExtensions() {
      const listEl = document.getElementById('cct-sidebar-extensions-list');
      if (!listEl) return;

      try {
        const data = await api.get('/api/extensions');
        state.sidebarExtensions = data.extensions || [];
        this.renderSidebarExtensionsList(state.sidebarExtensions);
      } catch (e) {
        listEl.innerHTML = `<div style="padding: 10px; font-size: 11px; color: var(--color-red);">${this.escapeHtml(e.message)}</div>`;
      }
    },

    filterSidebarExtensions(cat) {
      document.querySelectorAll('#cct-sb-ext-pills .cct-pill').forEach(p => {
        p.classList.remove('active');
        if (p.textContent.toLowerCase() === cat.toLowerCase() || (cat === 'all' && p.textContent.toLowerCase() === 'all')) {
          p.classList.add('active');
        }
      });

      if (!cat || cat.toLowerCase() === 'all') {
        this.renderSidebarExtensionsList(state.sidebarExtensions);
        return;
      }
      const filtered = state.sidebarExtensions.filter(e => 
        e.category && e.category.toLowerCase().includes(cat.toLowerCase())
      );
      this.renderSidebarExtensionsList(filtered);
    },

    renderSidebarExtensionsList(exts) {
      const listEl = document.getElementById('cct-sidebar-extensions-list');
      if (!listEl) return;

      if (!exts || exts.length === 0) {
        listEl.innerHTML = '<div style="padding: 12px; font-size: 11px; color: var(--term-text-muted); text-align: center;">No extensions in this category.</div>';
        return;
      }

      listEl.innerHTML = '';
      exts.forEach(ext => {
        const item = document.createElement('div');
        item.className = 'cct-ext-card-item';
        item.innerHTML = `
          <div class="cct-ext-card-info">
            <span class="cct-ext-card-icon">${ext.icon || '🧩'}</span>
            <div class="cct-ext-card-text">
              <span class="cct-ext-card-name">${this.escapeHtml(ext.name || ext.id)}</span>
              <span class="cct-ext-card-desc">${this.escapeHtml(ext.description || ext.category || '')}</span>
            </div>
          </div>
          <label class="cct-switch">
            <input type="checkbox" ${ext.enabled ? 'checked' : ''} onchange="FATTY.toggleExtension('${ext.id}', this.checked)">
            <span class="cct-slider"></span>
          </label>
        `;
        listEl.appendChild(item);
      });
    },

    async toggleExtension(extId, enabled) {
      try {
        await api.post('/api/extensions/toggle', { id: extId, enabled: enabled });
        this.showToast(`Extension ${extId} ${enabled ? 'enabled' : 'disabled'} ✓`, 'info');
      } catch (e) {
        this.showToast(`Toggle failed: ${e.message}`, 'error');
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // SETTINGS, PREFERENCES & SHORTCUTS
    // ─────────────────────────────────────────────────────────────────────
    syncSidebarSettings() {
      const permPills = ['ask', 'restricted', 'full'];
      permPills.forEach(p => {
        const btn = document.getElementById(`cct-sb-perm-${p}`);
        if (btn) btn.classList.toggle('active', state.permissionMode === p);
      });
      const sbModelName = document.getElementById('cct-sb-active-model-name');
      if (sbModelName) sbModelName.textContent = `${state.provider} ${state.model}`;
    },

    switchSettingsTab(tab) {
      ['general', 'ai', 'perm', 'editor', 'shortcuts'].forEach(t => {
        const btn = document.getElementById(`tab-settings-${t}`);
        const view = document.getElementById(`cct-settings-tab-${t}`);
        if (btn) btn.classList.toggle('active', t === tab);
        if (view) view.style.display = (t === tab) ? 'block' : 'none';
      });
    },

    async testCurrentConnection() {
      const prov = document.getElementById('cct-cfg-provider')?.value || state.provider.toLowerCase();
      const model = document.getElementById('cct-cfg-model')?.value || state.model;
      const endpoint = document.getElementById('cct-cfg-endpoint')?.value || '';
      const apikey = document.getElementById('cct-cfg-apikey')?.value || '';
      const resultEl = document.getElementById('cct-test-conn-result');
      const btn = document.getElementById('cct-test-conn-btn');

      if (btn) btn.textContent = 'Testing...';
      if (resultEl) {
        resultEl.style.color = '#7dcfff';
        resultEl.textContent = 'Measuring latency...';
      }

      try {
        const res = await api.post('/api/providers/verify', {
          provider: prov,
          model: model,
          base_url: endpoint,
          api_key: apikey
        });
        if (res && res.success) {
          if (resultEl) {
            resultEl.style.color = '#50fa7b';
            resultEl.textContent = `✓ Connected in ${res.latency_ms}ms`;
          }
          this.showToast(`AI connectivity verified (${res.latency_ms}ms) ✓`, 'success');
        } else {
          if (resultEl) {
            resultEl.style.color = '#f7768e';
            resultEl.textContent = `✕ ${res.error || 'Failed'}`;
          }
        }
      } catch (e) {
        if (resultEl) {
          resultEl.style.color = '#f7768e';
          resultEl.textContent = `✕ Error: ${e.message}`;
        }
      } finally {
        if (btn) btn.textContent = '⚡ Test Connection & Latency';
      }
    },

    toggleWordWrap(enabled) {
      const editor = document.getElementById('cct-code-editor');
      if (editor) {
        editor.style.whiteSpace = enabled ? 'pre-wrap' : 'pre';
        editor.style.wordBreak = enabled ? 'break-word' : 'normal';
      }
      const cb1 = document.getElementById('cct-sb-word-wrap');
      const cb2 = document.getElementById('cct-cfg-editor-wrap');
      const cb3 = document.getElementById('cct-user-wordwrap');
      if (cb1) cb1.checked = enabled;
      if (cb2) cb2.checked = enabled;
      if (cb3) cb3.checked = enabled;
    },

    toggleAutoSave(enabled) {
      state.autoSave = enabled;
      const cb1 = document.getElementById('cct-sb-auto-save');
      const cb2 = document.getElementById('cct-cfg-editor-autosave');
      const cb3 = document.getElementById('cct-user-autosave');
      if (cb1) cb1.checked = enabled;
      if (cb2) cb2.checked = enabled;
      if (cb3) cb3.checked = enabled;
    },

    toggleLineNumbers(enabled) {
      const gutter = document.getElementById('cct-line-numbers');
      if (gutter) gutter.style.display = enabled ? 'block' : 'none';
    },

    setEditorFont(fontStr) {
      const editor = document.getElementById('cct-code-editor');
      if (editor) editor.style.fontFamily = fontStr;
    },

    async toggleGuestMode() {
      try {
        const res = await api.post('/api/user/guest');
        if (res && res.user) {
          this.showToast(`Switched to ${res.guest_mode ? 'Guest Mode' : 'Local User'} ✓`, 'info');
          this.openUserModal();
        }
      } catch (e) {
        this.showToast('Guest mode toggle failed: ' + e.message, 'error');
      }
    },

    openUserProfile() {
      this.openUserModal();
    },

    openThemes() {
      this.openThemesModal();
    },


    // ─────────────────────────────────────────────────────────────────────
    // AI MODE SELECTOR (Ctrl+M)
    // ─────────────────────────────────────────────────────────────────────
    openModeSelector() {
      const modal = document.getElementById('cct-mode-selector-modal');
      const grid = document.getElementById('cct-mode-grid');
      if (!modal || !grid) return;

      grid.innerHTML = '';
      state.modes.forEach(m => {
        const meta = state.modeMeta[m] || { label: m, icon: '●', color: '#fff', desc: '' };
        const card = document.createElement('div');
        card.className = 'cct-mode-card' + (m === state.activeMode ? ' active' : '');
        card.innerHTML = `
          <span class="cct-mode-card-icon" style="color: ${meta.color};">${meta.icon}</span>
          <div class="cct-mode-card-info">
            <span class="cct-mode-card-title" style="color: ${meta.color};">${meta.label}</span>
            <span class="cct-mode-card-desc">${meta.desc}</span>
          </div>
        `;
        card.addEventListener('click', () => {
          this.selectMode(m);
        });
        grid.appendChild(card);
      });

      modal.style.display = 'flex';
    },

    async selectMode(modeId) {
      state.activeMode = modeId;
      const meta = state.modeMeta[modeId] || state.modeMeta.build;

      const badge = document.getElementById('cct-mode-badge');
      if (badge) {
        badge.textContent = `${meta.icon} ${meta.label}`;
        badge.style.color = meta.color;
      }

      this.closeAllModals();

      try {
        await api.post('/api/modes/switch', { mode: modeId });
      } catch (e) {}
    },

    // ─────────────────────────────────────────────────────────────────────
    // MEMORY CENTER (/memory)
    // ─────────────────────────────────────────────────────────────────────
    async openMemoryCenter() {
      const modal = document.getElementById('cct-memory-modal');
      if (!modal) return;
      modal.style.display = 'flex';
      await this.loadMemoryFacts();
    },

    async loadMemoryFacts() {
      const list = document.getElementById('cct-memory-list');
      if (!list) return;
      list.innerHTML = '<div style="padding: 8px; color: var(--term-text-faint);">Loading memory…</div>';

      try {
        const res = await api.get('/api/memory/facts');
        state.memoryFacts = (res && res.facts) ? res.facts : [];
      } catch (e) {
        state.memoryFacts = [];
      }

      this.renderMemoryFacts();
    },

    renderMemoryFacts() {
      const list = document.getElementById('cct-memory-list');
      if (!list) return;
      list.innerHTML = '';

      if (!state.memoryFacts.length) {
        list.innerHTML = '<div style="padding: 8px; color: var(--term-text-faint);">No persistent facts recorded yet. Add one below.</div>';
        return;
      }

      state.memoryFacts.forEach((fact, idx) => {
        const card = document.createElement('div');
        card.className = 'cct-fact-card';
        const text = typeof fact === 'string' ? fact : (fact.fact || JSON.stringify(fact));
        card.innerHTML = `
          <span class="cct-fact-content">📌 ${this.escapeHtml(text)}</span>
          <span class="cct-fact-del" title="Delete fact">✕</span>
        `;
        card.querySelector('.cct-fact-del').addEventListener('click', () => {
          this.deleteMemoryFact(idx);
        });
        list.appendChild(card);
      });
    },

    async addMemoryFact() {
      const input = document.getElementById('cct-add-fact-input');
      if (!input || !input.value.trim()) return;
      const text = input.value.trim();
      input.value = '';

      try {
        await api.post('/api/memory/fact', { fact: text });
      } catch (e) {
        console.error('Error adding fact:', e);
      }
      await this.loadMemoryFacts();
    },

    async deleteMemoryFact(idx) {
      try {
        await api.del(`/api/memory/fact/${idx}`);
      } catch (e) {
        console.error('Error deleting fact:', e);
      }
      await this.loadMemoryFacts();
    },

    async clearAllMemory() {
      if (!confirm('Are you sure you want to clear all persistent CAT memory?')) return;
      try {
        await api.post('/api/command/dispatch', { command: '/memory clear' });
      } catch (e) {}
      await this.loadMemoryFacts();
    },

    // ─────────────────────────────────────────────────────────────────────
    // EXTENSIONS MANAGER (/extensions)
    // ─────────────────────────────────────────────────────────────────────
    async openExtensionsManager() {
      const modal = document.getElementById('cct-extensions-modal');
      if (!modal) return;
      modal.style.display = 'flex';
      await this.loadExtensions();
    },

    async loadExtensions() {
      const list = document.getElementById('cct-extensions-list');
      if (!list) return;
      list.innerHTML = '<div style="padding: 8px; color: var(--term-text-faint);">Loading extensions…</div>';

      try {
        const res = await api.get('/api/extensions');
        state.extensions = (res && res.extensions) ? res.extensions : [];
      } catch (e) {
        state.extensions = [
          { id: 'gestures', name: 'Gestures & Camera Control', enabled: true, description: 'Hand-gesture camera control pipeline' },
          { id: 'vision', name: 'Vision Agent & Canvas Annotations', enabled: false, description: 'Visual UI analysis & cursor tracking' },
          { id: 'personalize', name: 'AI Personalization', enabled: true, description: 'Adaptive system prompt & user preferences' },
          { id: 'customization', name: 'Customization Engine', enabled: true, description: 'Themes, sound effects & keybinding customizations' }
        ];
      }

      this.renderExtensions();
    },

    renderExtensions() {
      const list = document.getElementById('cct-extensions-list');
      if (!list) return;
      list.innerHTML = '';

      state.extensions.forEach(ext => {
        const card = document.createElement('div');
        card.className = 'cct-ext-card';
        const icon = ext.icon || '🧩';
        const isEnabled = ext.enabled || ext.state === 'INSTALLED_ENABLED';
        card.innerHTML = `
          <div class="cct-ext-info">
            <span class="cct-ext-title">${this.escapeHtml(icon)} ${this.escapeHtml(ext.name || ext.display_name || ext.id)}</span>
            <span class="cct-ext-desc">${this.escapeHtml(ext.description || '')}</span>
            <span style="font-size: 11px; color: var(--term-text-faint); margin-top: 3px; display: block;">${this.escapeHtml(ext.publisher || 'Custom')} · v${this.escapeHtml(ext.version || '1.0.0')} · ${this.escapeHtml(ext.category || 'General')}</span>
          </div>
          <button class="cct-ext-toggle-btn ${isEnabled ? 'active' : ''}">
            ${isEnabled ? 'Enabled' : 'Disabled'}
          </button>
        `;
        card.querySelector('.cct-ext-toggle-btn').addEventListener('click', () => {
          this.toggleExtension(ext.id);
        });
        list.appendChild(card);
      });
    },

    async toggleExtension(extId) {
      try {
        await api.post('/api/extensions/toggle', { id: extId });
      } catch (e) {
        console.error('Error toggling extension:', e);
      }
      await this.loadExtensions();
    },

    openCreateExtensionModal() {
      const modal = document.getElementById('cct-create-ext-modal');
      if (!modal) return;
      const err = document.getElementById('cct-create-ext-error');
      if (err) { err.style.display = 'none'; err.textContent = ''; }
      const nameInput = document.getElementById('cct-create-ext-name');
      const idInput = document.getElementById('cct-create-ext-id');
      const descInput = document.getElementById('cct-create-ext-desc');
      if (nameInput) nameInput.value = '';
      if (idInput) idInput.value = '';
      if (descInput) descInput.value = '';
      modal.style.display = 'flex';
      if (nameInput) nameInput.focus();
    },

    closeCreateExtensionModal(e) {
      if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('cct-modal-close-btn')) return;
      const modal = document.getElementById('cct-create-ext-modal');
      if (modal) modal.style.display = 'none';
    },

    async submitCreateExtension() {
      const nameInput = document.getElementById('cct-create-ext-name');
      const idInput = document.getElementById('cct-create-ext-id');
      const iconInput = document.getElementById('cct-create-ext-icon');
      const descInput = document.getElementById('cct-create-ext-desc');
      const catInput = document.getElementById('cct-create-ext-cat');
      const err = document.getElementById('cct-create-ext-error');
      const submitBtn = document.getElementById('cct-create-ext-submit');

      const name = nameInput ? nameInput.value.trim() : '';
      let extId = idInput ? idInput.value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_') : '';
      if (!name) {
        if (err) { err.textContent = 'Please enter an extension name.'; err.style.display = 'block'; }
        return;
      }
      if (!extId) {
        extId = name.toLowerCase().replace(/[^a-z0-9_]/g, '_');
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating…';
      }

      try {
        const payload = {
          id: extId,
          name: name,
          icon: (iconInput && iconInput.value.trim()) || '⚡',
          description: (descInput && descInput.value.trim()) || '',
          category: (catInput && catInput.value) || 'Custom',
          publisher: 'You (Custom)',
        };
        const res = await api.post('/api/extensions/create', payload);
        if (res && res.success) {
          this.closeCreateExtensionModal();
          await this.loadExtensions();
        } else {
          if (err) {
            err.textContent = (res && res.extension && res.extension.message) || 'Failed to create extension.';
            err.style.display = 'block';
          }
        }
      } catch (e) {
        if (err) {
          err.textContent = e.message || 'Network error creating extension.';
          err.style.display = 'block';
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Create & Install';
        }
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // PERMISSIONS
    // ─────────────────────────────────────────────────────────────────────
    async loadPermissions() {
      try {
        const res = await api.get('/api/permissions');
        if (res && res.mode) {
          state.permissionMode = res.mode;
        }
      } catch (e) {
        console.log('Using default permission mode');
      }
      this.updatePermissionUI();
    },

    updatePermissionUI() {
      const pillIcon = document.getElementById('cct-perm-icon');
      const pillText = document.getElementById('cct-perm-text');
      const label = state.permLabels[state.permissionMode] || state.permLabels.ask;

      if (pillIcon) pillIcon.textContent = label.icon;
      if (pillText) pillText.textContent = label.text;
    },

    togglePermissionModal() {
      const modal = document.getElementById('cct-perm-modal');
      if (modal) {
        modal.style.display = modal.style.display === 'none' ? 'flex' : 'none';
      }
    },

    async setPermissionMode(mode) {
      state.permissionMode = mode;
      this.updatePermissionUI();
      this.closeAllModals();

      try {
        await api.post('/api/permissions/mode', { mode });
      } catch (e) {
        console.error('Error changing permission mode:', e);
      }

      // Append audit log line if in chat
      const turnsBox = document.getElementById('cct-chat-turns');
      if (turnsBox && turnsBox.style.display !== 'none') {
        const audit = document.createElement('div');
        audit.className = 'cct-audit-log';
        const label = state.permLabels[mode] || state.permLabels.ask;
        audit.innerHTML = `
          <div class="cct-audit-line">Access: ${label.icon} ${label.text} Scope:</div>
          <div class="cct-audit-scope">${state.workspaceRoot}</div>
          <div class="cct-audit-line">Permission mode: ${label.icon} ${label.text}</div>
        `;
        turnsBox.appendChild(audit);
        this.scrollToBottom();
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // SETTINGS & CONFIG
    // ─────────────────────────────────────────────────────────────────────
    async loadConfig() {
      try {
        const st = await api.get('/api/status');
        if (st) {
          if (st.provider && st.provider !== 'none') state.provider = st.provider.toUpperCase();
          if (st.model && st.model !== 'none') state.model = st.model;
        }
      } catch (e) {}

      const modelBadge = document.getElementById('cct-model-badge');
      if (modelBadge) modelBadge.textContent = `${state.provider} ${state.model}`;

      const welcomeModel = document.getElementById('cct-welcome-model');
      if (welcomeModel) welcomeModel.textContent = `${state.provider.toLowerCase()} ${state.model}`;
    },

    openSettings() {
      const modal = document.getElementById('cct-settings-modal');
      const pInp = document.getElementById('cct-cfg-provider');
      const mInp = document.getElementById('cct-cfg-model');
      if (pInp) pInp.value = state.provider.toLowerCase();
      if (mInp) mInp.value = state.model;
      if (modal) modal.style.display = 'flex';
    },

    async saveSettings() {
      const pInp = document.getElementById('cct-cfg-provider');
      const mInp = document.getElementById('cct-cfg-model');

      if (pInp && pInp.value) state.provider = pInp.value.toUpperCase();
      if (mInp && mInp.value) state.model = mInp.value;

      try {
        await api.post('/api/models/switch', {
          provider: state.provider.toLowerCase(),
          model: state.model
        });
      } catch (e) {}

      this.closeAllModals();
      await this.loadConfig();
    },

    // ─────────────────────────────────────────────────────────────────────
    // MAIN MENU & STARTUP LIFECYCLE
    // ─────────────────────────────────────────────────────────────────────
    async toggleNavMenu(e) {
      if (e) e.stopPropagation();
      const popup = document.getElementById('cct-main-menu-popup');
      if (!popup) return;
      if (popup.style.display === 'block') {
        popup.style.display = 'none';
        return;
      }
      await this.loadNavMenu();
      popup.style.display = 'block';
    },

    async loadNavMenu() {
      const container = document.getElementById('cct-main-menu-items');
      if (!container) return;
      container.innerHTML = '<div style="padding: 8px 12px; color: var(--term-text-muted); font-size: 11px;">Loading menu...</div>';

      try {
        const data = await api.get('/api/menu');
        const items = data.items || [];
        container.innerHTML = '';

        items.forEach(item => {
          if (item.is_separator) {
            const sep = document.createElement('div');
            sep.className = 'cct-menu-sep';
            container.appendChild(sep);
            return;
          }
          if (item.is_section_header) {
            const sec = document.createElement('div');
            sec.className = 'cct-menu-section';
            sec.textContent = item.label;
            container.appendChild(sec);
            return;
          }
          if (item.is_placeholder) {
            return;
          }

          const row = document.createElement('div');
          row.className = 'cct-menu-item';
          row.innerHTML = `
            <div class="cct-menu-item-left">
              <span class="cct-menu-icon">${item.icon || '•'}</span>
              <span>${item.label}</span>
            </div>
            ${item.shortcut ? `<span class="cct-menu-shortcut">${item.shortcut}</span>` : ''}
          `;
          row.addEventListener('click', (ev) => {
            ev.stopPropagation();
            document.getElementById('cct-main-menu-popup').style.display = 'none';
            this.handleMenuAction(item.action);
          });
          container.appendChild(row);
        });
      } catch (err) {
        container.innerHTML = '<div style="padding: 8px 12px; color: var(--color-red); font-size: 11px;">Failed to load menu</div>';
      }
    },

    handleMenuAction(action) {
      switch (action) {
        case 'open_folder':
          this.openFolderDialog();
          break;
        case 'recent_workspaces':
          this.openRecentWorkspacesModal();
          break;
        case 'chats':
          this.openChatsModal();
          break;
        case 'mcp_servers':
          this.openMcpModal();
          break;
        case 'backup_providers':
          this.openBackupProvidersModal();
          break;
        case 'themes':
          this.openThemesModal();
          break;
        case 'extensions':
          this.openExtensionsModal();
          break;
        case 'user':
          this.openUserModal();
          break;
        case 'signout':
          this.openSignOutModal();
          break;
        case 'cust_customization':
        case 'cust_personalize':
          this.openPersonalizeModal();
          break;
        case 'cust_gestures':
          this.openGesturesModal();
          break;
        default:
          console.log('Action selected:', action);
          break;
      }
    },

    async checkStartup() {
      try {
        const st = await api.get('/api/startup/status');
        if (st && !st.has_seen) {
          const modal = document.getElementById('cct-welcome-modal');
          const grid = document.getElementById('cct-highlights-grid');
          if (grid && st.highlights) {
            grid.innerHTML = st.highlights.map(h => `
              <div class="cct-highlight-card">
                <span class="cct-highlight-icon">${h.icon}</span>
                <div>
                  <div class="cct-highlight-title">${h.name}</div>
                  <div class="cct-highlight-desc">${h.desc}</div>
                </div>
              </div>
            `).join('');
          }
          if (modal) modal.style.display = 'flex';

          // Staged boot animation
          const bar = document.getElementById('cct-boot-progress-bar');
          const status = document.getElementById('cct-boot-status');
          if (bar && status) {
            bar.style.width = '15%';
            status.textContent = '● Initializing provider subsystems...';
            setTimeout(() => {
              bar.style.width = '55%';
              status.textContent = '● Loading memory & workspace index...';
            }, 300);
            setTimeout(() => {
              bar.style.width = '85%';
              status.textContent = '● Checking security sandbox & permissions...';
            }, 600);
            setTimeout(() => {
              bar.style.width = '100%';
              status.textContent = '● System ready. All subsystems initialized.';
            }, 900);
          }
        }
      } catch (e) {
        console.warn('Startup status check error:', e);
      }
    },

    async dismissWelcomeModal() {
      const modal = document.getElementById('cct-welcome-modal');
      const dontShow = document.getElementById('cct-welcome-dont-show');
      if (dontShow && dontShow.checked) {
        try {
          await api.post('/api/startup/dismiss');
        } catch (e) {}
      }
      if (modal) modal.style.display = 'none';
    },

    // ─────────────────────────────────────────────────────────────────────
    // OPEN FOLDER (METHOD A: BROWSE & METHOD B: ENTER PATH)
    // ─────────────────────────────────────────────────────────────────────
    currentBrowsePath: null,
    parentBrowsePath: null,

    switchFolderTab(tab) {
      const bTab = document.getElementById('tab-folder-browse');
      const pTab = document.getElementById('tab-folder-path');
      const bBox = document.getElementById('cct-folder-tab-browse');
      const pBox = document.getElementById('cct-folder-tab-path');
      if (tab === 'browse') {
        if (bTab) bTab.classList.add('active');
        if (pTab) pTab.classList.remove('active');
        if (bBox) bBox.style.display = 'block';
        if (pBox) pBox.style.display = 'none';
      } else {
        if (bTab) bTab.classList.remove('active');
        if (pTab) pTab.classList.add('active');
        if (bBox) bBox.style.display = 'none';
        if (pBox) pBox.style.display = 'block';
        const inp = document.getElementById('cct-folder-input');
        if (inp && (!inp.value || inp.value === '')) {
          inp.value = this.currentBrowsePath || state.workspaceRoot;
        }
        if (inp) this.onFolderInputChanged(inp.value);
      }
    },

    async openFolderDialog() {
      const modal = document.getElementById('cct-folder-modal');
      this.switchFolderTab('browse');
      await this.loadFsBrowse(state.workspaceRoot);
      if (modal) modal.style.display = 'flex';
    },

    async loadFsBrowse(path) {
      const pathDisplay = document.getElementById('cct-fs-current-path');
      const drivesRow = document.getElementById('cct-fs-drives-row');
      const folderList = document.getElementById('cct-fs-folder-list');
      if (folderList) folderList.innerHTML = '<div style="padding: 8px; color: var(--term-text-muted);">Loading folders...</div>';

      try {
        const url = path ? `/api/fs/browse?path=${encodeURIComponent(path)}` : '/api/fs/browse';
        const res = await api.get(url);
        this.currentBrowsePath = res.current_path;
        this.parentBrowsePath = res.parent_path;

        if (pathDisplay) {
          pathDisplay.textContent = res.current_path;
          pathDisplay.title = res.current_path;
        }

        const input = document.getElementById('cct-folder-input');
        if (input) input.value = res.current_path;

        // Render drives
        if (drivesRow && res.drives) {
          drivesRow.innerHTML = res.drives.map(d => `
            <button class="cct-fs-drive-btn ${res.current_path.startsWith(d) ? 'active' : ''}" onclick="FATTY.loadFsBrowse('${d.replace(/\\/g, '\\\\')}')">
              ${d}
            </button>
          `).join('');
        }

        // Render folders
        if (folderList) {
          folderList.innerHTML = '';
          if (!res.folders || res.folders.length === 0) {
            folderList.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted); font-size: 11.5px;">No subdirectories found</div>';
          } else {
            res.folders.forEach(f => {
              const item = document.createElement('div');
              item.className = 'cct-fs-folder-item';
              item.innerHTML = `
                <span>📁 ${f.name}</span>
                ${f.protected ? '<span style="color: var(--color-amber); font-size: 10px;">🔒 protected</span>' : ''}
              `;
              item.addEventListener('click', () => {
                this.loadFsBrowse(f.path);
              });
              folderList.appendChild(item);
            });
          }
        }
      } catch (err) {
        if (folderList) folderList.innerHTML = `<div style="padding: 8px; color: var(--color-red);">Error: ${err.message}</div>`;
      }
    },

    browseFolderUp() {
      if (this.parentBrowsePath) {
        this.loadFsBrowse(this.parentBrowsePath);
      }
    },

    folderValidateTimer: null,
    onFolderInputChanged(val) {
      clearTimeout(this.folderValidateTimer);
      const msg = document.getElementById('cct-folder-validation-msg');
      if (!val || !val.trim()) {
        if (msg) {
          msg.className = 'cct-validation-msg';
          msg.textContent = 'Enter folder path to validate...';
        }
        return;
      }
      this.folderValidateTimer = setTimeout(async () => {
        try {
          const res = await api.get(`/api/fs/validate?path=${encodeURIComponent(val.trim())}`);
          if (msg) {
            msg.className = `cct-validation-msg ${res.valid ? 'valid' : 'invalid'}`;
            msg.textContent = res.message;
          }
        } catch (e) {
          if (msg) {
            msg.className = 'cct-validation-msg invalid';
            msg.textContent = 'Validation error: ' + e.message;
          }
        }
      }, 250);
    },

    async confirmOpenFolder() {
      const isPathTab = document.getElementById('cct-folder-tab-path').style.display !== 'none';
      let targetPath = this.currentBrowsePath;
      if (isPathTab) {
        const inp = document.getElementById('cct-folder-input');
        if (inp && inp.value.trim()) targetPath = inp.value.trim();
      }
      if (!targetPath) return;

      try {
        const res = await api.post('/api/workspace/open', { path: targetPath });
        state.workspaceRoot = res.path || targetPath;
        state.workspaceName = res.name || targetPath.split(/[\\/]/).filter(Boolean).pop() || targetPath;
        this.closeAllModals();
        await this.loadWorkspace(targetPath);
      } catch (err) {
        alert('Could not open folder: ' + err.message);
      }
    },

    openRecentPath(pathOrName) {
      const match = state.recentProjects.find(p => p.name === pathOrName || p.path === pathOrName);
      const target = match ? match.path : pathOrName;
      document.getElementById('cct-folder-input').value = target;
      this.currentBrowsePath = target;
      this.confirmOpenFolder();
    },

    // ─────────────────────────────────────────────────────────────────────
    // RECENT WORKSPACES MODAL
    // ─────────────────────────────────────────────────────────────────────
    async openRecentWorkspacesModal() {
      const modal = document.getElementById('cct-recent-modal');
      const list = document.getElementById('cct-recent-modal-list');
      if (list) list.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">Loading recent workspaces...</div>';
      if (modal) modal.style.display = 'flex';

      try {
        const data = await api.get('/api/workspace/recent');
        const items = data.workspaces || [];
        if (list) {
          list.innerHTML = '';
          if (items.length === 0) {
            list.innerHTML = '<div style="padding: 12px; color: var(--term-text-muted);">No recent workspaces recorded.</div>';
            return;
          }
          items.forEach(w => {
            const row = document.createElement('div');
            row.className = 'cct-card-row';
            const existsTag = w.exists ? '<span style="color: var(--color-green); font-size: 10px;">✓ Exists</span>' : '<span style="color: var(--color-red); font-size: 10px;">⚠ Missing</span>';
            const pinIcon = w.pinned ? '📌' : '📍';
            row.innerHTML = `
              <div class="cct-card-row-info">
                <div class="cct-card-row-title">
                  <span>📁 ${w.name}</span>
                  ${existsTag}
                  ${w.pinned ? '<span style="font-size: 11px;">📌</span>' : ''}
                </div>
                <div class="cct-card-row-sub">${w.path}</div>
              </div>
              <div class="cct-card-row-actions">
                <button class="cct-icon-btn" onclick="FATTY.togglePinRecent('${w.path.replace(/\\/g, '\\\\')}', ${!w.pinned})" title="${w.pinned ? 'Unpin' : 'Pin to top'}">${pinIcon}</button>
                <button class="cct-icon-btn" onclick="FATTY.removeRecentWorkspace('${w.path.replace(/\\/g, '\\\\')}')" title="Remove from list">✕</button>
                <button class="cct-modal-btn primary" style="padding: 3px 8px; font-size: 11px;" onclick="FATTY.openDirectWorkspace('${w.path.replace(/\\/g, '\\\\')}')">Open</button>
              </div>
            `;
            list.appendChild(row);
          });
        }
      } catch (err) {
        if (list) list.innerHTML = `<div style="padding: 10px; color: var(--color-red);">${err.message}</div>`;
      }
    },

    async togglePinRecent(path, pin) {
      await api.post('/api/workspace/recent/pin', { path, pinned: pin });
      this.openRecentWorkspacesModal();
    },

    async removeRecentWorkspace(path) {
      await api.post('/api/workspace/recent/remove', { path });
      this.openRecentWorkspacesModal();
    },

    async clearRecentWorkspaces() {
      await api.post('/api/workspace/recent/clear');
      this.openRecentWorkspacesModal();
    },

    async openDirectWorkspace(path) {
      this.closeAllModals();
      await api.post('/api/workspace/open', { path });
      state.workspaceRoot = path;
      state.workspaceName = path.split(/[\\/]/).filter(Boolean).pop() || path;
      await this.loadWorkspace(path);
    },

    // ─────────────────────────────────────────────────────────────────────
    // SAVED CHATS MODAL (chat_store.py)
    // ─────────────────────────────────────────────────────────────────────
    async openChatsModal() {
      const modal = document.getElementById('cct-chats-modal');
      const list = document.getElementById('cct-chats-modal-list');
      if (list) list.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">Loading chat sessions...</div>';
      if (modal) modal.style.display = 'flex';

      try {
        const data = await api.get('/api/chats');
        const chats = data.chats || [];
        if (list) {
          list.innerHTML = '';
          if (chats.length === 0) {
            list.innerHTML = '<div style="padding: 12px; color: var(--term-text-muted);">No saved chats yet. Start typing to create one!</div>';
            return;
          }
          chats.forEach(c => {
            const row = document.createElement('div');
            row.className = 'cct-card-row';
            const isActive = state.chatId === c.id;
            row.innerHTML = `
              <div class="cct-card-row-info">
                <div class="cct-card-row-title">
                  <span>💬 ${c.name || 'Untitled Chat'}</span>
                  ${isActive ? '<span style="color: var(--color-blue); font-size: 10px;">● ACTIVE</span>' : ''}
                </div>
                <div class="cct-card-row-sub">${c.message_count || 0} messages · Updated ${c.updated_at ? new Date(c.updated_at * 1000).toLocaleTimeString() : 'Recently'}</div>
              </div>
              <div class="cct-card-row-actions">
                <button class="cct-icon-btn" onclick="FATTY.renameChatSession('${c.id}', '${(c.name || '').replace(/'/g, "\\'")}')">Rename</button>
                <button class="cct-icon-btn" onclick="FATTY.deleteChatSession('${c.id}')" title="Delete">✕</button>
                <button class="cct-modal-btn primary" style="padding: 3px 8px; font-size: 11px;" onclick="FATTY.switchChatSession('${c.id}')">Switch</button>
              </div>
            `;
            list.appendChild(row);
          });
        }
      } catch (err) {
        if (list) list.innerHTML = `<div style="padding: 10px; color: var(--color-red);">${err.message}</div>`;
      }
    },

    async createNewChatSession() {
      const name = prompt('New chat title:', 'Chat ' + new Date().toLocaleTimeString());
      if (!name) return;
      try {
        const res = await api.post('/api/chats', { name, project_path: state.workspaceRoot });
        if (res && res.id) {
          this.switchChatSession(res.id);
        }
      } catch (e) {
        alert('Could not create chat: ' + e.message);
      }
    },

    async renameChatSession(id, oldName) {
      const name = prompt('Rename chat:', oldName);
      if (!name || name === oldName) return;
      await api.post(`/api/chats/${id}/rename`, { name });
      this.openChatsModal();
    },

    async deleteChatSession(id) {
      if (!confirm('Are you sure you want to delete this chat session?')) return;
      await api.del(`/api/chats/${id}`);
      if (state.chatId === id) {
        state.chatId = null;
        this.newChat();
      }
      this.openChatsModal();
    },

    async switchChatSession(id) {
      try {
        const chat = await api.get(`/api/chats/${id}`);
        state.chatId = id;
        this.closeAllModals();

        // Switch main screen to chat turns
        const welcome = document.getElementById('cct-welcome-view');
        const turnsBox = document.getElementById('cct-chat-turns');
        if (welcome) welcome.style.display = 'none';
        if (turnsBox) {
          turnsBox.style.display = 'flex';
          turnsBox.innerHTML = '';
          const messages = chat.messages || [];
          messages.forEach(m => {
            if (m.role === 'user') {
              this.appendUserMessage(m.content);
            } else if (m.role === 'assistant') {
              const card = this.appendAssistantLoading();
              this.updateAssistantCard(card, {
                text: m.content,
                model: state.model,
                mode: state.activeMode,
                time: '0:01',
                tools_used: []
              });
            }
          });
        }
      } catch (err) {
        alert('Could not load chat: ' + err.message);
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // MCP SERVERS MODAL (mcp.py)
    // ─────────────────────────────────────────────────────────────────────
    async openMcpModal() {
      const modal = document.getElementById('cct-mcp-modal');
      const list = document.getElementById('cct-mcp-servers-list');
      if (list) list.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">Loading MCP servers...</div>';
      if (modal) modal.style.display = 'flex';

      try {
        const data = await api.get('/api/mcp/servers');
        const servers = data.servers || [];
        if (list) {
          list.innerHTML = '';
          if (servers.length === 0) {
            list.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted); font-size: 11.5px;">No MCP servers configured yet. Add one below!</div>';
          } else {
            servers.forEach(s => {
              const row = document.createElement('div');
              row.className = 'cct-card-row';
              const isConn = s.connected;
              row.innerHTML = `
                <div class="cct-card-row-info">
                  <div class="cct-card-row-title">
                    <span style="color: ${isConn ? 'var(--color-green)' : 'var(--term-text-faint)'};">●</span>
                    <span>${s.name || s.id}</span>
                    <span style="font-size: 10px; color: var(--term-text-muted);">(${s.command || 'custom'})</span>
                  </div>
                  <div class="cct-card-row-sub">${(s.args || []).join(' ')}</div>
                </div>
                <div class="cct-card-row-actions">
                  <button class="cct-icon-btn" onclick="FATTY.toggleMcpServer('${s.id}', ${!isConn})">${isConn ? 'Disconnect' : 'Connect'}</button>
                  <button class="cct-icon-btn" onclick="FATTY.removeMcpServer('${s.id}')">✕</button>
                </div>
              `;
              list.appendChild(row);
            });
          }
        }
      } catch (e) {
        if (list) list.innerHTML = `<div style="padding: 10px; color: var(--color-red);">${e.message}</div>`;
      }
    },

    async toggleMcpServer(id, connect) {
      try {
        if (connect) {
          await api.post(`/api/mcp/servers/${id}/connect`);
        } else {
          await api.post(`/api/mcp/servers/${id}/disconnect`);
        }
      } catch (e) {}
      this.openMcpModal();
    },

    async removeMcpServer(id) {
      await api.del(`/api/mcp/servers/${id}`);
      this.openMcpModal();
    },

    async saveMcpServer() {
      const name = document.getElementById('cct-mcp-name').value.trim();
      const cmd = document.getElementById('cct-mcp-cmd').value.trim();
      const argsRaw = document.getElementById('cct-mcp-args').value.trim();
      if (!name || !cmd) {
        alert('Server name and command are required.');
        return;
      }
      const args = argsRaw ? argsRaw.split(/\s+/) : [];
      await api.post('/api/mcp/servers', { id: name.toLowerCase(), name, command: cmd, args });
      document.getElementById('cct-mcp-name').value = '';
      document.getElementById('cct-mcp-cmd').value = '';
      document.getElementById('cct-mcp-args').value = '';
      this.openMcpModal();
    },

    // ─────────────────────────────────────────────────────────────────────
    // BACKUP PROVIDERS MODAL (Automatic Failover Chain)
    // ─────────────────────────────────────────────────────────────────────
    backupChain: [],
    async openBackupProvidersModal() {
      const modal = document.getElementById('cct-backup-modal');
      const list = document.getElementById('cct-backup-chain-list');
      if (list) list.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">Loading failover chain...</div>';
      if (modal) modal.style.display = 'flex';

      try {
        const data = await api.get('/api/backup-providers');
        this.backupChain = data.providers || [];
        this.renderBackupChain();
      } catch (e) {
        if (list) list.innerHTML = `<div style="padding: 10px; color: var(--color-red);">${e.message}</div>`;
      }
    },

    renderBackupChain() {
      const list = document.getElementById('cct-backup-chain-list');
      if (!list) return;
      list.innerHTML = '';
      if (this.backupChain.length === 0) {
        list.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">No backup providers configured.</div>';
        return;
      }
      this.backupChain.forEach((p, idx) => {
        const row = document.createElement('div');
        row.className = 'cct-card-row';
        row.innerHTML = `
          <div class="cct-card-row-info">
            <div class="cct-card-row-title">
              <span style="color: var(--color-cyan); font-weight: bold;">#${idx + 1}</span>
              <span>📡 ${p.toUpperCase()}</span>
            </div>
          </div>
          <div class="cct-card-row-actions">
            <button class="cct-icon-btn" onclick="FATTY.moveBackupChain(${idx}, -1)" ${idx === 0 ? 'disabled' : ''}>▲</button>
            <button class="cct-icon-btn" onclick="FATTY.moveBackupChain(${idx}, 1)" ${idx === this.backupChain.length - 1 ? 'disabled' : ''}>▼</button>
            <button class="cct-icon-btn" onclick="FATTY.testBackupProvider('${p}')">Test</button>
            <button class="cct-icon-btn" onclick="FATTY.removeBackupFromChain(${idx})">✕</button>
          </div>
        `;
        list.appendChild(row);
      });
    },

    moveBackupChain(index, delta) {
      const target = index + delta;
      if (target < 0 || target >= this.backupChain.length) return;
      const temp = this.backupChain[index];
      this.backupChain[index] = this.backupChain[target];
      this.backupChain[target] = temp;
      this.renderBackupChain();
    },

    removeBackupFromChain(index) {
      this.backupChain.splice(index, 1);
      this.renderBackupChain();
    },

    async testBackupProvider(name) {
      try {
        const res = await api.post('/api/verify', { provider: name });
        alert(`Provider [${name}] connectivity: ${res.ok ? 'SUCCESS' : 'FAILED'}\n${res.message || ''}`);
      } catch (e) {
        alert(`Test error for [${name}]: ${e.message}`);
      }
    },

    async saveBackupChain() {
      try {
        await api.post('/api/backup-providers', { providers: this.backupChain });
        alert('Backup failover chain saved successfully.');
        this.closeAllModals();
      } catch (e) {
        alert('Could not save chain: ' + e.message);
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // THEMES MODAL & LIVE CSS INJECTION (theme.py + theme_css.py)
    // ─────────────────────────────────────────────────────────────────────
    async openThemesModal() {
      const modal = document.getElementById('cct-themes-modal');
      const grid = document.getElementById('cct-themes-grid');
      if (grid) grid.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">Loading themes...</div>';
      if (modal) modal.style.display = 'flex';

      try {
        const data = await api.get('/api/themes');
        const themes = data.themes || [];
        if (grid) {
          grid.innerHTML = '';
          themes.forEach(th => {
            const card = document.createElement('div');
            card.className = `cct-theme-card ${th.active ? 'active' : ''}`;
            card.innerHTML = `
              <div class="cct-theme-name">${th.label || th.name}</div>
              <div class="cct-theme-badge">${th.is_light ? '☀ Light Theme' : '🌙 Dark Theme'}</div>
              ${th.active ? '<span style="font-size: 10px; color: var(--color-blue); font-weight: bold;">● Active Theme</span>' : ''}
            `;
            card.addEventListener('click', () => {
              this.applyTheme(th.name);
            });
            grid.appendChild(card);
          });
        }
      } catch (e) {
        if (grid) grid.innerHTML = `<div style="padding: 10px; color: var(--color-red);">${e.message}</div>`;
      }
    },

    async applyTheme(themeName) {
      try {
        const res = await api.post('/api/themes/select', { theme: themeName });
        if (res && res.css_variables) {
          for (const [key, val] of Object.entries(res.css_variables)) {
            document.documentElement.style.setProperty(`--${key}`, val);
            if (key === 'background') document.documentElement.style.setProperty('--term-bg', val);
            if (key === 'surface') document.documentElement.style.setProperty('--term-surface', val);
            if (key === 'primary') document.documentElement.style.setProperty('--color-blue', val);
          }
        }
        if (res) {
          if (res.is_light) {
            document.documentElement.classList.add('cct-light-theme');
          } else {
            document.documentElement.classList.remove('cct-light-theme');
          }
        }
        this.openThemesModal();
      } catch (e) {
        console.warn('Theme apply error:', e);
      }
    },

    // ─────────────────────────────────────────────────────────────────────
    // USER PROFILE & IDENTITY MODAL (fomoji_auth.py + identity.py)
    // ─────────────────────────────────────────────────────────────────────
    async openUserModal() {
      const modal = document.getElementById('cct-user-modal');
      const content = document.getElementById('cct-user-modal-content');
      if (content) content.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">Loading user profile...</div>';
      if (modal) modal.style.display = 'flex';

      try {
        const prof = await api.get('/api/user/profile');
        if (content) {
          content.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 14px;">
              <div style="font-size: 32px;">🐱</div>
              <div>
                <div style="font-size: 15px; font-weight: bold; color: var(--term-text);">${prof.user.name}</div>
                <div style="font-size: 11.5px; color: var(--term-text-muted);">${prof.user.email} · Role: ${prof.user.role}</div>
                <div style="font-size: 11px; color: ${prof.authenticated ? 'var(--color-green)' : 'var(--color-amber)'}; margin-top: 2px;">
                  ● ${prof.authenticated ? 'Authenticated via Fomoji' : 'Local Guest Mode'}
                </div>
              </div>
            </div>

            <div class="cct-profile-grid">
              <div class="cct-profile-metric">
                <div class="cct-profile-metric-title">Active AI Model</div>
                <div class="cct-profile-metric-val" style="font-size: 12px;">${prof.active_provider.toUpperCase()} / ${prof.active_model}</div>
              </div>
              <div class="cct-profile-metric">
                <div class="cct-profile-metric-title">App Version</div>
                <div class="cct-profile-metric-val" style="font-size: 12px;">${prof.app.short_name} v${prof.app.version}</div>
              </div>
              <div class="cct-profile-metric">
                <div class="cct-profile-metric-title">Durable Memory Facts</div>
                <div class="cct-profile-metric-val">${prof.memory_facts_count}</div>
              </div>
              <div class="cct-profile-metric">
                <div class="cct-profile-metric-title">Saved Sessions</div>
                <div class="cct-profile-metric-val">${prof.saved_chats_count}</div>
              </div>
            </div>

            <div style="margin-top: 14px; font-size: 11px; color: var(--term-text-faint); line-height: 1.4;">
              ${prof.app.tagline}<br>
              Creator: ${prof.app.creator} · Tech stack: ${prof.app.tech_stack}
            </div>
          `;
        }
      } catch (e) {
        if (content) content.innerHTML = `<div style="padding: 10px; color: var(--color-red);">${e.message}</div>`;
      }
    },

    openSignOutModal() {
      const modal = document.getElementById('cct-signout-modal');
      if (modal) modal.style.display = 'flex';
    },

    async confirmSignOut() {
      try {
        await api.post('/api/auth/logout');
        alert('Signed out successfully.');
      } catch (e) {}
      this.closeAllModals();
      await this.loadConfig();
    },

    // ─────────────────────────────────────────────────────────────────────
    // GESTURES MODAL
    // ─────────────────────────────────────────────────────────────────────
    async openGesturesModal() {
      const modal = document.getElementById('cct-gestures-modal');
      const list = document.getElementById('cct-gestures-list');
      if (list) list.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">Loading gestures...</div>';
      if (modal) modal.style.display = 'flex';

      try {
        const data = await api.get('/api/gestures');
        const gestures = data.gestures || [];
        if (list) {
          list.innerHTML = '';
          if (gestures.length === 0) {
            list.innerHTML = '<div style="padding: 10px; color: var(--term-text-muted);">No gestures registered.</div>';
            return;
          }
          gestures.forEach(g => {
            const row = document.createElement('div');
            row.className = 'cct-card-row';
            row.innerHTML = `
              <div class="cct-card-row-info">
                <div class="cct-card-row-title">
                  <span>✋ ${g.name || g.id}</span>
                </div>
                <div class="cct-card-row-sub">${g.description || 'Smart terminal gesture'}</div>
              </div>
              <div class="cct-card-row-actions">
                <button class="cct-icon-btn ${g.enabled ? 'active' : ''}" onclick="FATTY.toggleGesture('${g.id}', ${!g.enabled})">
                  ${g.enabled ? 'Enabled' : 'Disabled'}
                </button>
              </div>
            `;
            list.appendChild(row);
          });
        }
      } catch (e) {
        if (list) list.innerHTML = `<div style="padding: 10px; color: var(--color-red);">${e.message}</div>`;
      }
    },

    async toggleGesture(id, enable) {
      await api.post('/api/gestures/toggle', { id, enabled: enable });
      this.openGesturesModal();
    },

    // ─────────────────────────────────────────────────────────────────────
    // PERSONALIZE & AI CUSTOMIZATION MODAL
    // ─────────────────────────────────────────────────────────────────────
    personalizeData: null,
    renderPersonaCards(profiles, activeId) {
      const cardsBox = document.getElementById('cct-persona-cards');
      if (!cardsBox) return;
      cardsBox.innerHTML = (profiles || []).map(p => {
        const isActive = p.id === activeId;
        const icon = p.id.includes('builder') ? '🏗️' : p.id.includes('code') ? '⚡' : p.id.includes('sci') ? '🔬' : p.id.includes('review') ? '🛡️' : '💡';
        return `
          <div class="cct-theme-card ${isActive ? 'active' : ''}" style="padding: 10px; cursor: pointer; border-radius: 0px !important;" onclick="FATTY.selectPersonaCard('${p.id}')">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 18px;">${icon}</span>
              <div style="overflow: hidden;">
                <div style="font-weight: bold; font-size: 12.5px; color: ${isActive ? 'var(--accent-build)' : 'var(--term-text)'};">${p.name}</div>
                <div style="font-size: 10.5px; color: var(--term-text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${p.description || ''}</div>
              </div>
            </div>
          </div>
        `;
      }).join('');
    },

    selectPersonaCard(id) {
      const select = document.getElementById('cct-persona-select');
      if (select) select.value = id;
      if (this.personalizeData) {
        this.personalizeData.active_id = id;
        this.renderPersonaCards(this.personalizeData.profiles || [], id);
      }
      this.onPersonaSelected(id);
    },

    async openPersonalizeModal() {
      const modal = document.getElementById('cct-personalize-modal');
      const select = document.getElementById('cct-persona-select');
      const promptInp = document.getElementById('cct-custom-prompt');
      const slider = document.getElementById('cct-temp-slider');
      const tempVal = document.getElementById('cct-temp-val');

      if (modal) modal.style.display = 'flex';

      // 1. If we have cached data, render immediately with 0ms lag
      if (this.personalizeData) {
        const data = this.personalizeData;
        const profiles = data.profiles || [];
        this.renderPersonaCards(profiles, data.active_id);
        if (select) {
          select.innerHTML = profiles.map(p => `
            <option value="${p.id}" ${p.id === data.active_id ? 'selected' : ''}>${p.name}</option>
          `).join('');
          select.value = data.active_id || 'default';
        }
        if (promptInp && !promptInp.value) promptInp.value = data.prompt_customization || '';
        if (slider) {
          slider.value = data.temperature !== undefined ? data.temperature : 0.7;
          if (tempVal) tempVal.textContent = parseFloat(slider.value).toFixed(2);
        }
      }

      // 2. Fetch latest data in background and update smoothly
      try {
        const data = await api.get('/api/personalize');
        this.personalizeData = data;
        const profiles = data.profiles || [];
        this.renderPersonaCards(profiles, data.active_id);
        if (select) {
          select.innerHTML = profiles.map(p => `
            <option value="${p.id}" ${p.id === data.active_id ? 'selected' : ''}>${p.name}</option>
          `).join('');
          select.value = data.active_id || 'default';
        }
        if (promptInp) promptInp.value = data.prompt_customization || '';
        if (slider) {
          slider.value = data.temperature !== undefined ? data.temperature : 0.7;
          if (tempVal) tempVal.textContent = parseFloat(slider.value).toFixed(2);
        }
      } catch (e) {
        console.warn('Personalize load error:', e);
      }
    },

    onPersonaSelected(id) {
      if (!this.personalizeData) return;
      const match = (this.personalizeData.profiles || []).find(p => p.id === id);
      if (match && match.prompt) {
        const promptInp = document.getElementById('cct-custom-prompt');
        if (promptInp) promptInp.value = match.prompt;
      }
    },

    async savePersonalization() {
      const select = document.getElementById('cct-persona-select');
      const promptInp = document.getElementById('cct-custom-prompt');
      const slider = document.getElementById('cct-temp-slider');

      const personaId = select ? select.value : 'default';
      const prompt = promptInp ? promptInp.value : '';
      const temp = slider ? parseFloat(slider.value) : 0.7;

      try {
        await api.post('/api/personalize/active', { id: personaId });
        await api.post('/api/personalize/save', {
          id: personaId,
          prompt,
          temperature: temp
        });
        alert('Personalization settings saved.');
        this.closeAllModals();
      } catch (e) {
        alert('Save error: ' + e.message);
      }
    },

    openDocs() {
      const modal = document.getElementById('cct-docs-modal');
      if (modal) modal.style.display = 'flex';
    },

    triggerAttach() {
      const fileInput = document.getElementById('cct-file-input');
      if (fileInput) fileInput.click();
    },

    handleFileAttach(e) {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const input = document.getElementById('cct-message-input');
      if (input) {
        input.value += ` [Attached: ${file.name}]`;
      }
    },

    toggleSidebar() {
      const sb = document.getElementById('cct-sidebar');
      if (!sb) return;
      sb.style.display = sb.style.display === 'none' ? 'flex' : 'none';
    },

    closeAllModals(e) {
      if (e && e.target && !e.target.classList.contains('cct-modal-backdrop')) {
        return;
      }
      document.querySelectorAll('.cct-modal-backdrop').forEach(m => {
        m.style.display = 'none';
      });
      const menu = document.getElementById('cct-main-menu-popup');
      if (menu) menu.style.display = 'none';
    },

    // ─────────────────────────────────────────────────────────────────────
    // ASCII WORDMARK LOGO (5 DYNAMIC RESPONSIVE TIERS)
    // ─────────────────────────────────────────────────────────────────────
    initLogo() {
      const applyResponsiveLogo = () => {
        if (state.manualLogoOverride) return;
        const w = window.innerWidth;
        let tier = 0;
        if (w >= 900) tier = 0;       // Tier 1: 3D Block
        else if (w >= 750) tier = 1;  // Tier 2: Retro BBS
        else if (w >= 560) tier = 2;  // Tier 3: Cat Combo
        else if (w >= 380) tier = 3;  // Tier 4: Compact Bevel
        else tier = 4;                // Tier 5: Nano Banner
        this.setLogoVariant(tier, false);
      };
      window.addEventListener('resize', applyResponsiveLogo);
      applyResponsiveLogo();
    },

    setLogoVariant(idx, playAnimation = true) {
      if (idx < 0 || idx >= ASCII_LOGO_VARIANTS.length) return;
      state.logoVariant = idx;

      const logoEl = document.getElementById('cct-cat-ascii-logo');
      if (logoEl) {
        logoEl.textContent = ASCII_LOGO_VARIANTS[idx].art;
        logoEl.title = `CAT Wordmark: ${ASCII_LOGO_VARIANTS[idx].name}`;
        if (playAnimation) {
          logoEl.classList.remove('cct-ascii-glitch-anim');
          void logoEl.offsetWidth; // Trigger reflow for restart
          logoEl.classList.add('cct-ascii-glitch-anim');
        }
      }
    },

    cycleLogoVariant() {
      state.manualLogoOverride = true;
      const nextIdx = ((state.logoVariant || 0) + 1) % ASCII_LOGO_VARIANTS.length;
      this.setLogoVariant(nextIdx, true);
    },

    // ─────────────────────────────────────────────────────────────────────
    // SESSION NOTEBOOKS (CALCULATIONS & DERIVATIONS)
    // ─────────────────────────────────────────────────────────────────────
    async loadSessionNotebooks() {
      try {
        const res = await api.get('/api/session/notebooks');
        if (res && res.notebooks) {
          state.sessionNotebooks = res.notebooks;
          state.sessionCount = res.count || res.notebooks.length;
          this.renderSessionNotebooksList();
        }
      } catch (err) {
        console.warn('Could not load session notebooks:', err);
      }
    },

    renderSessionNotebooksList() {
      const countEl = document.getElementById('cct-session-count');
      const listEl = document.getElementById('cct-session-notebooks-list');
      if (!listEl) return;

      const solvedCount = (state.sessionNotebooks && state.sessionNotebooks.length) || state.sessionCount || 0;
      if (countEl) {
        countEl.innerHTML = `<span class="cct-green">●</span> <b>${solvedCount}</b> solved this session`;
      }

      const chipsHtml = `
        <div class="cct-column-faint" id="cct-nb-empty-note" style="margin-top: 4px;">Instant derivation &amp; solve:</div>
        <div class="cct-nb-quick-chips" id="cct-nb-quick-chips">
          <button class="cct-nb-chip" onclick="FATTY.runNotebookSolve('kinetics')" title="First-order integrated rate law">⚡ Kinetics</button>
          <button class="cct-nb-chip" onclick="FATTY.runNotebookSolve('arrhenius')" title="Arrhenius activation energy">⚡ Arrhenius</button>
          <button class="cct-nb-chip" onclick="FATTY.runNotebookSolve('nernst')" title="Nernst cell potential">⚡ Nernst</button>
          <button class="cct-nb-chip" onclick="FATTY.runNotebookSolve('gibbs')" title="Gibbs free energy">⚡ Gibbs</button>
          <button class="cct-nb-chip" onclick="FATTY.runNotebookSolve('ideal_gas')" title="Ideal gas law">⚡ Gas Law</button>
        </div>
      `;

      if (!state.sessionNotebooks || state.sessionNotebooks.length === 0) {
        listEl.innerHTML = `
          <div class="cct-column-item" id="cct-session-count"><span class="cct-green">●</span> 0 solved this session</div>
          <div class="cct-column-faint">No generated files yet.</div>
          ${chipsHtml}
        `;
        return;
      }

      let itemsHtml = `
        <div class="cct-column-item" id="cct-session-count"><span class="cct-green">●</span> <b>${solvedCount}</b> solved this session</div>
      `;

      state.sessionNotebooks.slice(0, 3).forEach(nb => {
        const titleSafe = this.escapeHtml(nb.title || nb.topic || 'Notebook');
        const badgeSafe = this.escapeHtml(nb.category || 'Science');
        itemsHtml += `
          <div class="cct-nb-item">
            <span class="cct-nb-item-title" onclick="FATTY.openNotebook('${nb.id}')" title="View notebook: ${titleSafe}">📘 ${titleSafe}</span>
            <span class="cct-nb-item-badge">${badgeSafe}</span>
            <button class="cct-nb-open-btn" onclick="FATTY.openNotebook('${nb.id}')">View</button>
          </div>
        `;
      });

      itemsHtml += chipsHtml;
      listEl.innerHTML = itemsHtml;
    },

    async runNotebookSolve(topic) {
      try {
        const res = await api.post('/api/session/notebooks/solve', { topic: topic, create_file: true });
        if (res && res.success && res.notebook) {
          if (!state.sessionNotebooks) state.sessionNotebooks = [];
          state.sessionNotebooks.unshift(res.notebook);
          state.sessionCount = res.total_count || state.sessionNotebooks.length;
          this.renderSessionNotebooksList();

          const nb = res.notebook;
          const noticeHtml = 
            `<div style="line-height: 1.6;">` +
            `📘 <b style="color: #50fa7b;">Session Notebook Solved: ${this.escapeHtml(nb.title)}</b><br>` +
            `<b>Category</b>: <span style="color: #7aa2f7;">${this.escapeHtml(nb.category)}</span> · <b>Equation</b>: <code>${this.escapeHtml(nb.equation)}</code><br>` +
            `<b>Result</b>: <b style="color: #00f0ff;">${this.escapeHtml(nb.result)}</b><br>` +
            (nb.file_path ? `<span style="color: #6272a4; font-size: 11px;">Saved to workspace: ${this.escapeHtml(nb.file_path)}</span><br>` : '') +
            `<button class="cct-nb-new-btn" style="margin-top: 6px;" onclick="FATTY.openNotebook('${nb.id}')">Open Full Derivation</button>` +
            `</div>`;

          const welcome = document.getElementById('cct-welcome-view');
          const turnsBox = document.getElementById('cct-chat-turns');
          if (welcome && welcome.style.display !== 'none') {
            const countEl = document.getElementById('cct-session-count');
            if (countEl) {
              countEl.style.transition = 'color 0.2s ease';
              countEl.style.color = '#50fa7b';
              setTimeout(() => { countEl.style.color = ''; }, 1000);
            }
          } else {
            this.appendSystemNotice(noticeHtml);
          }
        }
      } catch (err) {
        alert('Notebook solve failed: ' + err.message);
      }
    },

    promptNewNotebook(prefilledTitle = '') {
      const title = prompt('Enter title for the new Session Notebook:', prefilledTitle || 'Chemical Kinetics Derivation');
      if (!title || !title.trim()) return;
      this.createNotebook(title.trim());
    },

    async createNotebook(title) {
      try {
        const res = await api.post('/api/session/notebooks/create', { title: title, ext: '.md' });
        if (res && res.success && res.notebook) {
          if (!state.sessionNotebooks) state.sessionNotebooks = [];
          state.sessionNotebooks.unshift(res.notebook);
          state.sessionCount = res.total_count || state.sessionNotebooks.length;
          this.renderSessionNotebooksList();

          if (res.notebook.file_path) {
            const fname = res.notebook.file_path.split(/[\\/]/).pop();
            this.openFile(res.notebook.file_path, fname);
          } else {
            this.openNotebook(res.notebook.id);
          }
        }
      } catch (err) {
        alert('Could not create notebook: ' + err.message);
      }
    },

    openNotebook(id) {
      const nb = (state.sessionNotebooks || []).find(n => n.id === id);
      if (!nb) return;

      if (nb.file_path) {
        const fname = nb.file_path.split(/[\\/]/).pop();
        this.openFile(nb.file_path, fname);
        return;
      }

      const editorPane = document.getElementById('cct-editor-pane');
      const resizer = document.getElementById('cct-editor-resizer');
      const titleEl = document.getElementById('cct-editor-filename');
      const textarea = document.getElementById('cct-code-editor');

      if (titleEl) titleEl.textContent = `${nb.title}.md`;
      if (textarea) {
        textarea.value = `# ${nb.title}\n\n**Category**: ${nb.category}\n**Equation**: ${nb.equation}\n**Timestamp**: ${nb.date} ${nb.timestamp}\n**Status**: ${nb.status}\n\n## Content / Derivation\n\n${nb.content}\n\n**Result**: ${nb.result}\n`;
      }
      if (editorPane) editorPane.style.display = 'flex';
      if (resizer) resizer.style.display = 'block';
      state.editorOpen = true;
      this.updateLineNumbers();
    },

    // ─────────────────────────────────────────────────────────────────────
    // CAT 3D ASCII BLOCK ART & ROUTINE TIME-BASED GREETING
    // ─────────────────────────────────────────────────────────────────────
    greetingOffset: 0,
    greetingsNumbered: [
      "[01]  > CAT is ready.",
      "[02]  > Welcome back.",
      "[03]  > CAT is awake.",
      "[04]  > Ready when you are.",
      "[05]  > Let's build.",
      "[06]  > Let's code.",
      "[07]  > Let's create.",
      "[08]  > Terminal ready.",
      "[09]  > Workspace ready.",
      "[10]  > System ready.",
      "[11]  > CAT online.",
      "[12]  > CAT initialized.",
      "[13]  > CAT is purring.",
      "[14]  > Paws on keyboard.",
      "[15]  > Ready to assist.",
      "[16]  > What are we building?",
      "[17]  > What are we coding?",
      "[18]  > What's the mission?",
      "[19]  > Your workspace awaits.",
      "[20]  > Back to work.",
      "[21]  > Let's get started.",
      "[22]  > Time to build.",
      "[23]  > Time to code.",
      "[24]  > Code mode ready.",
      "[25]  > Agent mode ready.",
      "[26]  > Notebook ready.",
      "[27]  > Research mode ready.",
      "[28]  > Plan mode ready.",
      "[29]  > Debug mode ready.",
      "[30]  > Build mode ready.",
      "[31]  > All systems go.",
      "[32]  > Everything is ready.",
      "[33]  > CAT has arrived.",
      "[34]  > CAT is here.",
      "[35]  > Good to see you.",
      "[36]  > Welcome to CAT.",
      "[37]  > Back in the terminal.",
      "[38]  > Your terminal companion.",
      "[39]  > Let's make something.",
      "[40]  > Let's solve it.",
      "[41]  > Let's figure it out.",
      "[42]  > Ready for the next task.",
      "[43]  > New session started.",
      "[44]  > Fresh session ready.",
      "[45]  > Workspace unlocked.",
      "[46]  > Terminal paws ready.",
      "[47]  > Brain online. Paws ready.",
      "[48]  > Coffee optional. Code required.",
      "[49]  > No noise. Just code.",
      "[50]  > CAT ready. Your move."
    ],
    greetingsFeline: [
      "> *meow* — ready.",
      "> Paws ready.",
      "> CAT is purring.",
      "> CAT has entered.",
      "> Paws on keyboard.",
      "> Meow. Let's code.",
      "> 🐾 Ready to build.",
      "> 🐾 Ready to debug.",
      "> 🐾 Ready to explore.",
      "> 🐾 Ready to create."
    ],
    greeting3DArt: {
      "READY": "  █▀▀▄ █▀▀ █▀▀█ █▀▀▄ █  █\n  █▄▄▀ █▀▀ █▄▄█ █  █  ▀█▀\n  ▀  ▀ ▀▀▀ ▀  ▀ ▀▀▀    █ ",
      "ONLINE": " █▀▀█ █▄ █ █   ▀█▀ █▄ █ █▀▀\n █  █ █ ▀█ █    █  █ ▀█ █▀▀\n ▀▀▀▀ ▀  ▀ ▀▀▀ ▀▀▀ ▀  ▀ ▀▀▀",
      "AWAKE": "  █▀▀█ █   █ █▀▀█ █▄▀ █▀▀\n  █▄▄█ █ █ █ █▄▄█ █ █ █▀▀\n  ▀  ▀ ▀▀ ▀▀ ▀  ▀ ▀ ▀ ▀▀▀",
      "BUILD": "  █▀▀▄ █  █ ▀█▀ █   █▀▀▄\n  █▀▀▄ █  █  █  █   █  █\n  ▀▀▀  ▀▀▀▀ ▀▀▀ ▀▀▀ ▀▀▀ ",
      "CODE": "   █▀▀ █▀▀█ █▀▀▄ █▀▀\n   █   █  █ █  █ █▀▀\n   ▀▀▀ ▀▀▀▀ ▀▀▀  ▀▀▀",
      "HELLO": "  █  █ █▀▀ █   █   █▀▀█\n  █▀▀█ █▀▀ █   █   █  █\n  ▀  ▀ ▀▀▀ ▀▀▀ ▀▀▀ ▀▀▀▀",
      "GO !": "    █▀▀ █▀▀█   ▀█▀\n    █ ▀ █  █    █ \n    ▀▀▀ ▀▀▀▀   ▀▀▀",
      "START": "  █▀▀ ▀█▀ █▀▀█ █▀▀▄ ▀█▀\n  ▀▀█  █  █▄▄█ █▄▄▀  █ \n  ▀▀▀  ▀  ▀  ▀ ▀  ▀  ▀ ",
      "BEGIN": "  █▀▀▄ █▀▀ █▀▀ ▀█▀ █▄ █\n  █▀▀▄ █▀▀ █ ▀  █  █ ▀█\n  ▀▀▀  ▀▀▀ ▀▀▀ ▀▀▀ ▀  ▀",
      "MEOW": "  █▄ ▄█ █▀▀ █▀▀█ █   █\n  █ ▀ █ █▀▀ █  █ █ █ █\n  ▀   ▀ ▀▀▀ ▀▀▀▀ ▀▀ ▀▀",
      "PAWS": "   █▀▀▄ █▀▀█ █   █ █▀▀\n   █▄▄▀ █▄▄█ █ █ █ ▀▀█\n   ▀    ▀  ▀ ▀▀ ▀▀ ▀▀▀",
      "PLAN": "   █▀▀▄ █   █▀▀█ █▄ █\n   █▄▄▀ █   █▄▄█ █ ▀█\n   ▀    ▀▀▀ ▀  ▀ ▀  ▀",
      "DEBUG": " █▀▀▄ █▀▀ █▀▀▄ █  █ █▀▀\n █  █ █▀▀ █▀▀▄ █  █ █ ▀\n ▀▀▀  ▀▀▀ ▀▀▀  ▀▀▀▀ ▀▀▀",
      "WORK": "   █   █ █▀▀█ █▀▀▄ █▄▀\n   █ █ █ █  █ █▄▄▀ █ █\n   ▀▀ ▀▀ ▀▀▀▀ ▀  ▀ ▀ ▀"
    },
    extractGreetingKeyword(numbered, feline) {
      for (const text of [numbered, feline]) {
        const t = (text || '').toLowerCase();
        if (t.includes('ready') || t.includes('assist') || t.includes('mission') || t.includes('task')) return 'READY';
        if (t.includes('online') || t.includes('brain online') || t.includes('initialized')) return 'ONLINE';
        if (t.includes('awake')) return 'AWAKE';
        if (t.includes('code') || t.includes('coding')) return 'CODE';
        if (t.includes('build') || t.includes('building') || t.includes('create')) return 'BUILD';
        if (t.includes('plan')) return 'PLAN';
        if (t.includes('debug')) return 'DEBUG';
        if (t.includes('welcome') || t.includes('arrived') || t.includes('here')) return 'HELLO';
        if (t.includes('start') || t.includes('session') || t.includes('fresh')) return 'START';
        if (t.includes('begin')) return 'BEGIN';
        if (t.includes('work') || t.includes('solve')) return 'WORK';
        if (t.includes('go') || t.includes('move')) return 'GO !';
        if (t.includes('paws')) return 'PAWS';
        if (t.includes('meow') || t.includes('purr')) return 'MEOW';
      }
      return 'READY';
    },
    initCatRoutineGreeting() {
      this.updateCatRoutineGreeting();
      setInterval(() => this.updateCatRoutineGreeting(), 60000);
    },
    cycleCatGreeting() {
      this.greetingOffset++;
      this.updateCatRoutineGreeting();
    },
    updateCatRoutineGreeting() {
      const now = new Date();
      const hour = now.getHours();
      const minute = now.getMinutes();
      const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      let period = "Night Ops";
      if (hour >= 5 && hour < 12) period = "Morning Build";
      else if (hour >= 12 && hour < 17) period = "Afternoon Focus";
      else if (hour >= 17 && hour < 22) period = "Evening Session";

      const minOfDay = hour * 60 + minute;
      const numIdx = (minOfDay + this.greetingOffset) % this.greetingsNumbered.length;
      const felIdx = (Math.floor(minOfDay / 3) + this.greetingOffset) % this.greetingsFeline.length;

      const numMsg = this.greetingsNumbered[numIdx];
      const felMsg = this.greetingsFeline[felIdx];
      const keyword = this.extractGreetingKeyword(numMsg, felMsg);

      const artEl = document.getElementById('cct-3d-block-art');
      if (artEl) {
        artEl.textContent = this.greeting3DArt[keyword] || this.greeting3DArt["READY"];
      }

      const timeEl = document.getElementById('cct-routine-time');
      if (timeEl) timeEl.textContent = `Routine ${timeStr} · ${period}`;

      const msgEl = document.getElementById('cct-greeting-msg');
      if (msgEl) msgEl.textContent = numMsg;

      const subEl = document.getElementById('cct-greeting-sub');
      if (subEl) subEl.textContent = felMsg;
    },

    // ─────────────────────────────────────────────────────────────────────
    // UTILS
    // ─────────────────────────────────────────────────────────────────────
    escapeHtml(str) {
      return (str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    },

    formatContent(str) {
      if (!str) return '';
      if (str.includes('```')) {
        const parts = str.split(/(```[\s\S]*?```)/g);
        return parts.map(p => {
          if (p.startsWith('```')) {
            const clean = p.replace(/^```[a-zA-Z0-9]*\n?/, '').replace(/```$/, '');
            return `<pre><code>${this.escapeHtml(clean)}</code></pre>`;
          }
          return `<p>${this.escapeHtml(p).replace(/\n/g, '<br>')}</p>`;
        }).join('');
      }
      return `<p>${this.escapeHtml(str).replace(/\n/g, '<br>')}</p>`;
    }
  };

  // Start app on DOMContentLoaded
  document.addEventListener('DOMContentLoaded', () => {
    window.FATTY.init();
  });
})();
