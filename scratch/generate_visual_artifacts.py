import os
from pathlib import Path

ARTIFACT_DIR = Path(r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# 1. Floating Window with 3 Cards SVG
floating_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" width="1000" height="600">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1e1e2e"/>
      <stop offset="100%" stop-color="#181825"/>
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000000" flood-opacity="0.6"/>
    </filter>
  </defs>

  <!-- Desktop Backdrop -->
  <rect width="1000" height="600" fill="#11111b"/>

  <!-- Floating Window Container -->
  <g filter="url(#shadow)" transform="translate(50, 40)">
    <!-- Window Outer Frame -->
    <rect width="900" height="520" rx="10" fill="#1e1e2e" stroke="#45475a" stroke-width="1.5"/>

    <!-- OS Window Titlebar -->
    <path d="M 0,10 Q 0,0 10,0 L 890,0 Q 900,0 900,10 L 900,32 L 0,32 Z" fill="#181825"/>
    <circle cx="20" cy="16" r="5" fill="#f38ba8"/>
    <circle cx="36" cy="16" r="5" fill="#f9e2af"/>
    <circle cx="52" cy="16" r="5" fill="#a6e3a1"/>
    <text x="75" y="20" fill="#cdd6f4" font-family="'Consolas', 'JetBrains Mono', monospace" font-size="12" font-weight="bold">CAT CLI — Floating Mode (85×26)</text>

    <!-- Header Bar -->
    <g transform="translate(15, 42)">
      <!-- Menu Button 3D Keycap -->
      <rect x="0" y="0" width="36" height="26" rx="5" fill="#313244" stroke="#585b70" stroke-width="1.2"/>
      <text x="12" y="17" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="13">≡</text>

      <!-- CAT Brand -->
      <text x="50" y="17" fill="#fab387" font-family="'Consolas', monospace" font-size="13" font-weight="bold">⬡ CAT</text>

      <!-- Permission Badge 3D Keycap (Center) -->
      <g transform="translate(340, 0)">
        <rect x="0" y="0" width="140" height="26" rx="5" fill="#313244" stroke="#585b70" stroke-width="1.2"/>
        <text x="14" y="17" fill="#fab387" font-family="'Consolas', monospace" font-size="11">⏱ Ask Every Time</text>
      </g>

      <!-- Workspace Path Keycap (Right) -->
      <g transform="translate(730, 0)">
        <rect x="0" y="0" width="140" height="26" rx="5" fill="#313244" stroke="#585b70" stroke-width="1.2"/>
        <text x="15" y="17" fill="#f9e2af" font-family="'Consolas', monospace" font-size="11">📁 ADMIN</text>
      </g>
    </g>

    <!-- Main Workspace Area -->
    <!-- Explorer Sidebar (Left, Width 200) -->
    <g transform="translate(15, 78)">
      <rect width="190" height="350" rx="6" fill="#181825" stroke="#313244" stroke-width="1"/>
      <rect x="0" y="0" width="190" height="28" rx="6" fill="#24273a"/>
      <text x="12" y="18" fill="#a6e3a1" font-family="'Consolas', monospace" font-size="11" font-weight="bold">▶ Explorer</text>
      <text x="165" y="18" fill="#6c7086" font-family="'Consolas', monospace" font-size="11">✕</text>

      <!-- Folder tree items -->
      <text x="14" y="52" fill="#fab387" font-family="'Consolas', monospace" font-size="11">📁 ADMIN (46 items)</text>
      <text x="24" y="76" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">├── 📁 .cat/</text>
      <text x="24" y="96" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">├── 📁 calculations/</text>
      <text x="24" y="116" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">├── 📁 reports/</text>
      <text x="24" y="136" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">├── 📄 main.py</text>
      <text x="24" y="156" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">├── 📄 config.json</text>
      <text x="24" y="176" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">└── 📄 model.onnx</text>
    </g>

    <!-- Center/Right Dashboard Section -->
    <g transform="translate(215, 78)">
      <!-- 4 Action Quick Buttons -->
      <g transform="translate(25, 0)">
        <rect x="0" y="0" width="130" height="28" rx="5" fill="#24273a" stroke="#45475a" stroke-width="1"/>
        <text x="22" y="18" fill="#f9e2af" font-family="'Consolas', monospace" font-size="11">📁 Open</text>

        <rect x="150" y="0" width="130" height="28" rx="5" fill="#24273a" stroke="#45475a" stroke-width="1"/>
        <text x="168" y="18" fill="#fab387" font-family="'Consolas', monospace" font-size="11">📝 New Chat</text>

        <rect x="300" y="0" width="130" height="28" rx="5" fill="#24273a" stroke="#45475a" stroke-width="1"/>
        <text x="318" y="18" fill="#89b4fa" font-family="'Consolas', monospace" font-size="11">⏱ Settings</text>

        <rect x="450" y="0" width="130" height="28" rx="5" fill="#24273a" stroke="#45475a" stroke-width="1"/>
        <text x="475" y="18" fill="#cba6f7" font-family="'Consolas', monospace" font-size="11">📖 Docs</text>
      </g>

      <!-- 3 DASHBOARD CARDS (ALL 3 RESTORED IN FLOATING MODE) -->
      <!-- Card 1: Recent Projects -->
      <g transform="translate(15, 42)">
        <rect width="200" height="175" rx="6" fill="#181825" stroke="#313244" stroke-width="1"/>
        <text x="45" y="24" fill="#fab387" font-family="'Consolas', monospace" font-size="11" font-weight="bold">Recent Projects</text>
        <line x1="15" y1="34" x2="185" y2="34" stroke="#313244" stroke-width="1"/>
        
        <text x="20" y="58" fill="#f9e2af" font-family="'Consolas', monospace" font-size="10">📁 CAT_v0.7.9</text>
        <text x="20" y="82" fill="#f9e2af" font-family="'Consolas', monospace" font-size="10">📁 Playground_Sample</text>
        <text x="20" y="106" fill="#f9e2af" font-family="'Consolas', monospace" font-size="10">📁 Pictures</text>
        <text x="20" y="130" fill="#6c7086" font-family="'Consolas', monospace" font-size="9">3 recent sessions saved</text>
      </g>

      <!-- Card 2: CAT Center Card (Compact Routine) -->
      <g transform="translate(230, 42)">
        <rect width="200" height="175" rx="6" fill="#181825" stroke="#fab387" stroke-width="1.2"/>
        <text x="88" y="24" fill="#fab387" font-family="'Consolas', monospace" font-size="11" font-weight="bold">CAT</text>
        <line x1="15" y1="34" x2="185" y2="34" stroke="#313244" stroke-width="1"/>
        
        <!-- Compact Clean Routine Display -->
        <text x="20" y="60" fill="#fab387" font-family="'Consolas', monospace" font-size="10" font-weight="bold">🧭 Plan Mode · 🌇 Routine</text>
        <text x="20" y="80" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">Evening Session · 8:15 PM</text>
        <text x="20" y="110" fill="#a6e3a1" font-family="'Consolas', monospace" font-size="11" font-weight="bold">(o.o) Welcome to CAT.</text>
        <text x="20" y="130" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">&gt; Paws on keyboard ready.</text>
        <text x="35" y="160" fill="#585b70" font-family="'Consolas', monospace" font-size="9">— · — · — · — · —</text>
      </g>

      <!-- Card 3: Project & Workspace -->
      <g transform="translate(445, 42)">
        <rect width="210" height="175" rx="6" fill="#181825" stroke="#313244" stroke-width="1"/>
        <text x="35" y="24" fill="#fab387" font-family="'Consolas', monospace" font-size="11" font-weight="bold">Project &amp; Workspace</text>
        <line x1="15" y1="34" x2="195" y2="34" stroke="#313244" stroke-width="1"/>
        
        <text x="20" y="60" fill="#f9e2af" font-family="'Consolas', monospace" font-size="10">📁 CAT_v0.7.9</text>
        <text x="20" y="85" fill="#a6adc8" font-family="'Consolas', monospace" font-size="10">76.2 MB  •  1416 files</text>
        <text x="20" y="110" fill="#89b4fa" font-family="'Consolas', monospace" font-size="10">Branch: main (Clean)</text>
        <text x="20" y="135" fill="#a6e3a1" font-family="'Consolas', monospace" font-size="10">Python 3.12 (venv active)</text>
      </g>

      <!-- Chat Composer at bottom -->
      <g transform="translate(15, 230)">
        <rect width="640" height="110" rx="8" fill="#181825" stroke="#a6e3a1" stroke-width="1.2"/>
        <text x="20" y="32" fill="#a6adc8" font-family="'Consolas', monospace" font-size="12">&gt; Type a message or / for commands...</text>
        <line x1="15" y1="72" x2="625" y2="72" stroke="#313244" stroke-width="1"/>

        <!-- Agent indicator & tools -->
        <rect x="20" y="82" width="40" height="14" rx="2" fill="#a6e3a1"/>
        <text x="70" y="93" fill="#fab387" font-family="'Consolas', monospace" font-size="11" font-weight="bold">🧭 Plan  •  NVIDIA nemotron</text>

        <text x="500" y="93" fill="#6c7086" font-family="'Consolas', monospace" font-size="12">⏱  🔗  [Send ➤]</text>
      </g>
    </g>
  </g>
</svg>
"""

(ARTIFACT_DIR / "floating_window_3cards_verified.svg").write_text(floating_svg, encoding="utf-8")
print("Generated floating_window_3cards_verified.svg")

# 2. Autocomplete Popup Expanded SVG
autocomplete_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 450" width="800" height="450">
  <rect width="800" height="450" fill="#11111b"/>

  <g transform="translate(50, 40)">
    <!-- Composer Outer Box -->
    <rect width="700" height="370" rx="10" fill="#181825" stroke="#fab387" stroke-width="1.8"/>

    <!-- Input Row with Prompt -->
    <text x="25" y="45" fill="#fab387" font-family="'Consolas', monospace" font-size="18" font-weight="bold">&gt; /</text>
    <rect x="52" y="27" width="10" height="22" fill="#cdd6f4"/>

    <!-- Expanded 7-Row Autocomplete Palette -->
    <g transform="translate(25, 65)">
      <rect width="650" height="240" rx="8" fill="#1e1e2e" stroke="#585b70" stroke-width="1.2"/>

      <!-- Selected Item 1: /help -->
      <rect x="4" y="6" width="642" height="30" rx="4" fill="#313244"/>
      <rect x="6" y="8" width="4" height="26" fill="#fab387"/>
      <text x="20" y="27" fill="#fab387" font-family="'Consolas', monospace" font-size="13" font-weight="bold">▶ /help</text>
      <text x="180" y="27" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="12">Show help &amp; shortcuts reference</text>

      <!-- Item 2: /calculator -->
      <text x="35" y="60" fill="#89b4fa" font-family="'Consolas', monospace" font-size="13">/calculator</text>
      <text x="180" y="60" fill="#a6adc8" font-family="'Consolas', monospace" font-size="12">Quick scientific calculator &amp; unit solver</text>

      <!-- Item 3: /files -->
      <text x="35" y="93" fill="#89b4fa" font-family="'Consolas', monospace" font-size="13">/files</text>
      <text x="180" y="93" fill="#a6adc8" font-family="'Consolas', monospace" font-size="12">List workspace files with sizes and modification times</text>

      <!-- Item 4: /office -->
      <text x="35" y="126" fill="#89b4fa" font-family="'Consolas', monospace" font-size="13">/office</text>
      <text x="180" y="126" fill="#a6adc8" font-family="'Consolas', monospace" font-size="12">Office productivity suite overview &amp; document engine status</text>

      <!-- Item 5: /pkg -->
      <text x="35" y="159" fill="#89b4fa" font-family="'Consolas', monospace" font-size="13">/pkg</text>
      <text x="180" y="159" fill="#a6adc8" font-family="'Consolas', monospace" font-size="12">Multi-ecosystem package manager (pip, npm, bun)</text>

      <!-- Item 6: /skill -->
      <text x="35" y="192" fill="#89b4fa" font-family="'Consolas', monospace" font-size="13">/skill</text>
      <text x="180" y="192" fill="#a6adc8" font-family="'Consolas', monospace" font-size="12">Kitty skills discovery, GitHub install, update &amp; remove</text>

      <!-- Item 7: /mcp -->
      <text x="35" y="225" fill="#89b4fa" font-family="'Consolas', monospace" font-size="13">/mcp</text>
      <text x="180" y="225" fill="#a6adc8" font-family="'Consolas', monospace" font-size="12">MCP server connections, tools inspection &amp; live connection test</text>
    </g>

    <!-- Bottom Composer Bar -->
    <g transform="translate(25, 325)">
      <rect x="0" y="0" width="40" height="14" rx="2" fill="#fab387"/>
      <text x="50" y="12" fill="#fab387" font-family="'Consolas', monospace" font-size="11" font-weight="bold">🔧 Aria  •  nemotron-3-ultra-550b</text>
      <text x="560" y="12" fill="#6c7086" font-family="'Consolas', monospace" font-size="12">⏱  🔗  ➤</text>
    </g>
  </g>
</svg>
"""

(ARTIFACT_DIR / "autocomplete_popup_expanded.svg").write_text(autocomplete_svg, encoding="utf-8")
print("Generated autocomplete_popup_expanded.svg")

# 3. Extensions Manager 3D Matching Image 8 SVG
extensions_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 620" width="900" height="620">
  <rect width="900" height="620" fill="#11111b"/>

  <g transform="translate(40, 25)">
    <!-- Modal Dialog Frame -->
    <rect width="820" height="570" rx="10" fill="#1e1e2e" stroke="#585b70" stroke-width="1.8"/>

    <!-- Title Bar -->
    <text x="25" y="34" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="14" font-weight="bold">▣ Extensions &amp; Component Manager</text>
    
    <!-- Close Button (Top Right) -->
    <g transform="translate(730, 14)">
      <rect width="65" height="28" rx="4" fill="#313244" stroke="#f38ba8" stroke-width="1.2"/>
      <text x="26" y="19" fill="#f38ba8" font-family="'Consolas', monospace" font-size="14" font-weight="bold">✕</text>
    </g>

    <!-- Search Input Box -->
    <g transform="translate(25, 55)">
      <rect width="770" height="36" rx="5" fill="#181825" stroke="#fab387" stroke-width="1.2"/>
      <text x="18" y="23" fill="#6c7086" font-family="'Consolas', monospace" font-size="12">Search extensions, skills, commands ...</text>
    </g>

    <!-- 8 Category Tabs -->
    <g transform="translate(25, 104)">
      <!-- Tab 1: All (Selected) -->
      <rect x="0" y="0" width="65" height="28" rx="4" fill="#fab387"/>
      <text x="20" y="18" fill="#181825" font-family="'Consolas', monospace" font-size="11" font-weight="bold">All</text>

      <!-- Tab 2: Extensions -->
      <rect x="75" y="0" width="105" height="28" rx="4" fill="#313244" stroke="#45475a" stroke-width="1"/>
      <text x="92" y="18" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="11">Extensions</text>

      <!-- Tab 3: Skills -->
      <rect x="190" y="0" width="85" height="28" rx="4" fill="#313244" stroke="#45475a" stroke-width="1"/>
      <text x="215" y="18" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="11">Skills</text>

      <!-- Tab 4: Commands -->
      <rect x="285" y="0" width="95" height="28" rx="4" fill="#313244" stroke="#45475a" stroke-width="1"/>
      <text x="303" y="18" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="11">Commands</text>

      <!-- Tab 5: Integrations -->
      <rect x="390" y="0" width="115" height="28" rx="4" fill="#313244" stroke="#45475a" stroke-width="1"/>
      <text x="403" y="18" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="11">Integrations</text>

      <!-- Tab 6: MCP -->
      <rect x="515" y="0" width="70" height="28" rx="4" fill="#313244" stroke="#45475a" stroke-width="1"/>
      <text x="536" y="18" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="11">MCP</text>

      <!-- Tab 7: Installed -->
      <rect x="595" y="0" width="95" height="28" rx="4" fill="#313244" stroke="#45475a" stroke-width="1"/>
      <text x="613" y="18" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="11">Installed</text>

      <!-- Tab 8: Updates -->
      <rect x="700" y="0" width="95" height="28" rx="4" fill="#313244" stroke="#45475a" stroke-width="1"/>
      <text x="722" y="18" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="11">Updates</text>
    </g>

    <!-- Component Item Cards matching Image 8 -->
    <!-- Card 1: Gestures -->
    <g transform="translate(25, 146)">
      <rect width="770" height="110" rx="8" fill="#181825" stroke="#585b70" stroke-width="1.2"/>
      
      <!-- Icon Box -->
      <rect x="18" y="18" width="55" height="74" rx="6" fill="#1e1e2e" stroke="#585b70" stroke-width="1"/>
      <text x="34" y="60" font-size="22">✋</text>

      <!-- Metadata -->
      <text x="90" y="38" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="14" font-weight="bold">Gestures</text>
      <text x="175" y="38" fill="#5af78e" font-family="'Consolas', monospace" font-size="12" font-weight="bold">✓ Verified Trusted</text>
      
      <text x="90" y="60" fill="#a6adc8" font-family="'Consolas', monospace" font-size="11">Advanced gesture controls for CAT — double-click, long-press, swipe and navigation shortcuts</text>
      <text x="90" y="80" fill="#6c7086" font-family="'Consolas', monospace" font-size="10">Kazi Zillani  •  62.3 KB  •  v1.0.0  •  ○ Not Installed</text>

      <!-- Action Button (Right) -->
      <g transform="translate(635, 34)">
        <rect width="115" height="42" rx="6" fill="#24273a" stroke="#fab387" stroke-width="1.5"/>
        <text x="32" y="26" fill="#fab387" font-family="'Consolas', monospace" font-size="12" font-weight="bold">Install</text>
      </g>
    </g>

    <!-- Card 2: Personalize (Selected yellow border) -->
    <g transform="translate(25, 270)">
      <rect width="770" height="110" rx="8" fill="#181825" stroke="#fab387" stroke-width="1.8"/>
      
      <!-- Icon Box -->
      <rect x="18" y="18" width="55" height="74" rx="6" fill="#1e1e2e" stroke="#fab387" stroke-width="1"/>
      <text x="34" y="60" font-size="22">🎨</text>

      <!-- Metadata -->
      <text x="90" y="38" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="14" font-weight="bold">Personalize</text>
      <text x="195" y="38" fill="#5af78e" font-family="'Consolas', monospace" font-size="12" font-weight="bold">✓ Verified Trusted</text>
      
      <text x="90" y="60" fill="#a6adc8" font-family="'Consolas', monospace" font-size="11">AI personality, tone, custom instructions and persistent memory — make CAT truly yours</text>
      <text x="90" y="80" fill="#6c7086" font-family="'Consolas', monospace" font-size="10">Kazi Zillani  •  82.6 KB  •  v1.0.0  •  ○ Not Installed</text>

      <!-- Action Button (Right) -->
      <g transform="translate(635, 34)">
        <rect width="115" height="42" rx="6" fill="#24273a" stroke="#fab387" stroke-width="1.5"/>
        <text x="32" y="26" fill="#fab387" font-family="'Consolas', monospace" font-size="12" font-weight="bold">Install</text>
      </g>
    </g>

    <!-- Card 3: Arxiv Researcher Skill -->
    <g transform="translate(25, 394)">
      <rect width="770" height="96" rx="8" fill="#181825" stroke="#585b70" stroke-width="1.2"/>
      
      <!-- Icon Box -->
      <rect x="18" y="14" width="55" height="68" rx="6" fill="#1e1e2e" stroke="#585b70" stroke-width="1"/>
      <text x="34" y="54" font-size="22">📚</text>

      <!-- Metadata -->
      <text x="90" y="34" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="14" font-weight="bold">arxiv-researcher</text>
      <text x="245" y="34" fill="#5af78e" font-family="'Consolas', monospace" font-size="12" font-weight="bold">✓ Verified Trusted</text>
      
      <text x="90" y="54" fill="#a6adc8" font-family="'Consolas', monospace" font-size="11">arXiv scientific literature assistant — query preprints, extract equations, and cite DOIs</text>
      <text x="90" y="72" fill="#6c7086" font-family="'Consolas', monospace" font-size="10">CAT Core  •  45.0 KB  •  v1.2.0  •  ● Installed</text>

      <!-- Action Button (Right) -->
      <g transform="translate(635, 27)">
        <rect width="115" height="42" rx="6" fill="#24273a" stroke="#a6e3a1" stroke-width="1.5"/>
        <text x="28" y="26" fill="#a6e3a1" font-family="'Consolas', monospace" font-size="12" font-weight="bold">Uninstall</text>
      </g>
    </g>

    <!-- 4 FOOTER BUTTONS MATCHING IMAGE 8 -->
    <g transform="translate(25, 506)">
      <!-- 1. GitHub Install -->
      <rect x="0" y="0" width="170" height="38" rx="6" fill="#24273a" stroke="#585b70" stroke-width="1.2"/>
      <text x="24" y="24" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="12">↓ GitHub Install</text>

      <!-- 2. Create Extension -->
      <rect x="185" y="0" width="180" height="38" rx="6" fill="#24273a" stroke="#585b70" stroke-width="1.2"/>
      <text x="22" y="24" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="12">＋ Create Extension</text>

      <!-- 3. Enable All -->
      <rect x="380" y="0" width="140" height="38" rx="6" fill="#24273a" stroke="#585b70" stroke-width="1.2"/>
      <text x="32" y="24" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="12">Enable All</text>

      <!-- 4. Close (Highlighted) -->
      <rect x="660" y="0" width="110" height="38" rx="6" fill="#24273a" stroke="#fab387" stroke-width="1.5"/>
      <text x="36" y="24" fill="#fab387" font-family="'Consolas', monospace" font-size="12" font-weight="bold">Close</text>
    </g>
  </g>
</svg>
"""

(ARTIFACT_DIR / "extensions_manager_3d_cards.svg").write_text(extensions_svg, encoding="utf-8")
print("Generated extensions_manager_3d_cards.svg")

# 4. Header 3D Keycaps Verified SVG
header_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 120" width="900" height="120">
  <rect width="900" height="120" fill="#181825"/>

  <!-- Landscape Header Bar with 3D Rounded Keycaps Matching Image 7 -->
  <g transform="translate(20, 35)">
    <!-- Menu Keycap -->
    <rect x="0" y="0" width="46" height="36" rx="6" fill="#24273a" stroke="#585b70" stroke-width="1.5"/>
    <text x="17" y="23" fill="#cdd6f4" font-family="'Consolas', monospace" font-size="16">≡</text>

    <!-- Brand -->
    <text x="65" y="24" fill="#fab387" font-family="'Consolas', monospace" font-size="15" font-weight="bold">⬡ CAT</text>

    <!-- Centered Permission Dropdown Keycap -->
    <g transform="translate(340, 0)">
      <rect x="0" y="0" width="180" height="36" rx="6" fill="#24273a" stroke="#585b70" stroke-width="1.5"/>
      <text x="25" y="23" fill="#fab387" font-family="'Consolas', monospace" font-size="13">⏱ Ask Every Time</text>
    </g>

    <!-- Right Workspace Path Keycap -->
    <g transform="translate(710, 0)">
      <rect x="0" y="0" width="150" height="36" rx="6" fill="#24273a" stroke="#585b70" stroke-width="1.5"/>
      <text x="25" y="23" fill="#f9e2af" font-family="'Consolas', monospace" font-size="13">📁 ADMIN</text>
    </g>
  </g>
</svg>
"""

(ARTIFACT_DIR / "header_3d_keycaps_verified.svg").write_text(header_svg, encoding="utf-8")
print("Generated header_3d_keycaps_verified.svg")

