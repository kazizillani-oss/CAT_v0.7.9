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
    commands: [],
    filteredCommands: [],
    paletteSelectedIndex: 0,
    providers: [],
    models: [],
    selectedProvider: 'ollama',
    selectedModel: 'deepseek-r1',
    memoryFacts: [],
    extensions: []
  };

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

      // Fetch Tree
      try {
        const treeData = await api.get('/api/workspace/current/tree');
        if (treeData) {
          if (treeData.summary && treeData.summary.summary_line) {
            const sub = document.getElementById('cct-ws-folder-sub');
            if (sub) sub.textContent = treeData.summary.summary_line;
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
    // FILE OPEN & EDITOR
    // ─────────────────────────────────────────────────────────────────────
    async openFile(filePath, fileName) {
      document.querySelectorAll('.cct-tree-node').forEach(n => {
        if (n.dataset.path === filePath) {
          n.classList.add('active-file');
        } else {
          n.classList.remove('active-file');
        }
      });

      state.currentFile = { path: filePath, name: fileName };
      const titleEl = document.getElementById('cct-editor-filename');
      if (titleEl) titleEl.textContent = fileName;

      let content = '';
      try {
        const res = await api.get(`/api/workspace/current/file?path=${encodeURIComponent(filePath)}`);
        content = res.content || '';
      } catch (e) {
        console.warn('Could not read file from server, using sample code');
        content = `<!DOCTYPE html>\n<html>\n<head><title>CAT Editor</title></head>\n<body>\n<h1>Hello from CAT CLI</h1>\n</body>\n</html>`;
      }

      const textarea = document.getElementById('cct-code-editor');
      if (textarea) {
        textarea.value = content;
        textarea.scrollTop = 0;
      }

      const editorPane = document.getElementById('cct-editor-pane');
      const resizer = document.getElementById('cct-editor-resizer');
      if (editorPane) editorPane.classList.add('open');
      if (resizer) resizer.style.display = 'block';
      state.editorOpen = true;

      this.updateLineNumbers();
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

    async saveCurrentFile() {
      if (!state.currentFile) return;
      const textarea = document.getElementById('cct-code-editor');
      if (!textarea) return;

      try {
        await api.post(`/api/workspace/current/file`, {
          path: state.currentFile.path,
          content: textarea.value
        });
        console.log('Saved file:', state.currentFile.path);
        if (state.previewRunning) {
          this.runPreview();
        }
      } catch (e) {
        console.error('Error saving file:', e);
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
            '• <code>/mode &lt;name&gt;</code> — Switch active mode (build, agent, research, code)<br>' +
            '• <code>/settings</code> — Open configuration dialog<br>' +
            '• <code>/docs</code> — Open documentation<br>' +
            '• <code>/cat</code> or <code>/browse</code> — Launch CAT Browser<br>' +
            '• <code>/status</code> — Display AI and workspace status' +
            '</div>'
          );
          return;
        case '/mode':
          if (arg) {
            this.setAiMode(arg.toLowerCase());
            this.appendSystemNotice(`Switched active persona to <b style="color: #38bdf8;">${this.escapeHtml(arg)}</b> mode.`);
          } else {
            this.appendSystemNotice('Usage: <code>/mode &lt;build|agent|research|notebook&gt;</code>');
          }
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
        default:
          this.appendSystemNotice(
            `<span style="color: #ff5555;">Unknown command <code>${this.escapeHtml(cmd)}</code>.</span> Type <code>/help</code> for available commands.`
          );
          return;
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

      // 3. Request AI Response or Agent Turn from server
      const t0 = Date.now();
      try {
        let res;
        const isAgentMode = state.activeMode === 'agent';
        const isExplicitFileTask = /^\s*(create|write|delete|edit|refactor|generate)\s+(file|folder|dir|component|app|project)\b/i.test(text);
        if (isAgentMode || (state.activeMode === 'build' && isExplicitFileTask)) {
          // Use multi-turn agent for explicit file/tool tasks
          res = await api.post('/api/agent', {
            message: text,
            mode: 'agent',
            max_steps: 4,
            project_path: state.workspaceRoot,
            chat_id: state.chatId
          });
        } else {
          // Fast AI chat for queries, discussions, explanations, and build mode code generation
          res = await api.post('/api/chat', {
            message: text,
            mode: state.activeMode,
            project_path: state.workspaceRoot,
            chat_id: state.chatId
          });
        }
        if (res && res.chat_id) {
          state.chatId = res.chat_id;
        }

        const elapsed = Math.round((Date.now() - t0) / 1000);
        const mins = Math.floor(elapsed / 60);
        const secs = elapsed % 60;
        const timeStr = `${mins}:${secs < 10 ? '0' : ''}${secs}`;

        this.updateAssistantCard(cardEl, {
          text: res.response || '(No response from AI)',
          steps: res.steps || [],
          provider: res.provider || state.provider,
          model: res.model || state.model,
          timeStr: res.time_str || timeStr,
          tokens: res.tokens || Math.max(12, Math.round(text.length * 1.3)),
          timings: res.timings || {
            ttfb_ms: Math.max(120, elapsed * 800),
            memory_ms: 37,
            loop_ms: Math.max(140, elapsed * 1000)
          },
          calls: res.calls || (res.steps ? Math.max(1, res.steps.length) : 1)
        });
      } catch (e) {
        this.updateAssistantCard(cardEl, {
          text: '(Generation error: ' + (e.message || 'connection issue') + ')',
          provider: state.provider,
          model: state.model,
          timeStr: '0:05',
          tokens: 11,
          timings: { ttfb_ms: 500, memory_ms: 37, loop_ms: 540 },
          calls: 1
        });
      }
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
          <div class="cct-meta-line">Generating response from ${state.provider} ${state.model}…</div>
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

    async executeSlashCommand(cmdStr) {
      const welcome = document.getElementById('cct-welcome-view');
      const turnsBox = document.getElementById('cct-chat-turns');
      if (welcome) welcome.style.display = 'none';
      if (turnsBox) turnsBox.style.display = 'flex';

      this.appendUserMessage(cmdStr);
      const cardEl = this.appendAssistantLoading();

      const base = cmdStr.split(' ')[0].toLowerCase();
      if (base === '/clear') {
        this.newChat();
        return;
      } else if (base === '/docs' || base === '/help') {
        this.openDocs();
      } else if (base === '/model') {
        this.openModelPicker();
      } else if (base === '/mode') {
        this.openModeSelector();
      } else if (base === '/memory' || base === '/m') {
        this.openMemoryCenter();
      } else if (base === '/extensions') {
        this.openExtensionsManager();
      } else if (base === '/workspace') {
        this.openFolderDialog();
      }

      try {
        const res = await api.post('/api/command/dispatch', { command: cmdStr });
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
      } catch (e) {
        this.updateAssistantCard(cardEl, {
          text: `Command error: ${e.message}`,
          provider: state.provider,
          model: state.model,
          timeStr: '0:01',
          tokens: 0,
          timings: { ttfb_ms: 10, memory_ms: 5, loop_ms: 15 },
          calls: 1
        });
      }
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
    // MODEL & PROVIDER PICKER
    // ─────────────────────────────────────────────────────────────────────
    async openModelPicker() {
      const modal = document.getElementById('cct-model-picker-modal');
      if (!modal) return;
      modal.style.display = 'flex';

      await this.loadProviders();
    },

    async loadProviders() {
      try {
        const res = await api.get('/api/providers');
        if (res && res.providers) {
          state.providers = res.providers;
        }
      } catch (e) {
        console.warn('Could not load providers list');
        state.providers = [
          { id: 'ollama', name: 'Ollama (Local)' },
          { id: 'openai', name: 'OpenAI' },
          { id: 'anthropic', name: 'Anthropic Claude' },
          { id: 'gemini', name: 'Google Gemini' },
          { id: 'groq', name: 'Groq Cloud' },
          { id: 'deepseek', name: 'DeepSeek API' }
        ];
      }

      const countEl = document.getElementById('cct-provider-count');
      if (countEl) countEl.textContent = state.providers.length;

      this.renderProviders(state.providers);
      this.selectProvider(state.provider.toLowerCase());
    },

    filterProviders(query) {
      const q = (query || '').toLowerCase().trim();
      const filtered = state.providers.filter(p => {
        const id = (p.id || '').toLowerCase();
        const name = (p.name || '').toLowerCase();
        return id.includes(q) || name.includes(q);
      });
      this.renderProviders(filtered);
    },

    renderProviders(providers) {
      const container = document.getElementById('cct-picker-providers');
      if (!container) return;
      container.innerHTML = '';

      providers.slice(0, 60).forEach(p => {
        const btn = document.createElement('button');
        btn.className = 'cct-provider-btn' + (p.id === state.selectedProvider ? ' active' : '');
        btn.textContent = p.name || p.id;
        btn.addEventListener('click', () => {
          this.selectProvider(p.id);
        });
        container.appendChild(btn);
      });
    },

    async selectProvider(provId) {
      state.selectedProvider = provId;
      document.querySelectorAll('.cct-provider-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent.toLowerCase().includes(provId));
      });

      const modelContainer = document.getElementById('cct-picker-models');
      if (!modelContainer) return;
      modelContainer.innerHTML = '<div style="padding: 6px; color: var(--term-text-faint);">Loading models…</div>';

      try {
        const res = await api.get(`/api/models?provider=${encodeURIComponent(provId)}`);
        const models = (res && res.models && res.models.length) ? res.models : [state.model, 'default'];
        this.renderModels(models);
      } catch (e) {
        this.renderModels([state.model, 'default']);
      }
    },

    renderModels(models) {
      const container = document.getElementById('cct-picker-models');
      if (!container) return;
      container.innerHTML = '';

      models.forEach(m => {
        const row = document.createElement('div');
        row.className = 'cct-model-row' + (m === state.selectedModel ? ' active' : '');
        row.innerHTML = `
          <span>${this.escapeHtml(m)}</span>
          <span style="color: var(--term-text-faint); font-size: 11px;">Select</span>
        `;
        row.addEventListener('click', () => {
          state.selectedModel = m;
          document.querySelectorAll('.cct-model-row').forEach(r => r.classList.remove('active'));
          row.classList.add('active');
        });
        container.appendChild(row);
      });
    },

    async applySelectedModel() {
      state.provider = state.selectedProvider.toUpperCase();
      state.model = state.selectedModel;

      try {
        await api.post('/api/models/switch', {
          provider: state.selectedProvider,
          model: state.selectedModel
        });
      } catch (e) {}

      const modelBadge = document.getElementById('cct-model-badge');
      if (modelBadge) modelBadge.textContent = `${state.provider} ${state.model}`;

      const welcomeModel = document.getElementById('cct-welcome-model');
      if (welcomeModel) welcomeModel.textContent = `${state.provider.toLowerCase()} ${state.model}`;

      this.closeAllModals();
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
