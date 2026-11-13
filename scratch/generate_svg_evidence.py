import os
from pathlib import Path

ARTIFACT_DIR = Path(r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18")

def generate_header_3d_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 160" width="1024" height="160">
  <defs>
    <filter id="bevel" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
    <linearGradient id="headerGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1e1e2e"/>
      <stop offset="100%" stop-color="#181825"/>
    </linearGradient>
    <linearGradient id="btnRaised" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#313244"/>
      <stop offset="100%" stop-color="#24273a"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1024" height="160" fill="#181825"/>
  <rect x="0" y="0" width="1024" height="158" fill="url(#headerGrad)"/>
  <line x1="0" y1="159" x2="1024" y2="159" stroke="#313244" stroke-width="2"/>

  <!-- Left: 3D Menu Button [ ≡ ] -->
  <g transform="translate(24, 40)">
    <!-- 3D Bevel Box -->
    <rect x="0" y="0" width="60" height="48" rx="4" fill="#24273a"/>
    <!-- Top & Left Light Bevel -->
    <path d="M 4 2 L 56 2 Q 58 2 58 4 L 58 46 L 56 46 L 56 4 L 4 4 Z" fill="#7a7f9a"/>
    <!-- Bottom & Right Dark Bevel -->
    <path d="M 4 46 L 56 46 L 56 4 L 58 4 L 58 46 Q 58 48 56 48 L 4 48 Z" fill="#11111b"/>
    <text x="30" y="32" font-family="Consolas, monospace" font-size="24" font-weight="bold" fill="#cdd6f4" text-anchor="middle">≡</text>
  </g>

  <!-- Brand Mark & Logo -->
  <g transform="translate(104, 40)">
    <text x="0" y="34" font-family="Consolas, monospace" font-size="28" font-weight="900" fill="#fab387">⬡ CAT</text>
  </g>

  <!-- Center: 3D Permission Pill [ ⏱ Ask Every Time ] -->
  <g transform="translate(412, 40)">
    <rect x="0" y="0" width="200" height="48" rx="6" fill="#24273a"/>
    <!-- Top & Left Highlight -->
    <path d="M 6 2 L 194 2 Q 198 2 198 6 L 198 44 L 196 44 L 196 4 L 6 4 Z" fill="#7a7f9a"/>
    <!-- Bottom & Right Shadow -->
    <path d="M 6 46 L 194 46 L 194 4 L 198 4 L 198 44 Q 198 48 194 48 L 6 48 Z" fill="#11111b"/>
    <text x="100" y="31" font-family="Consolas, monospace" font-size="16" font-weight="bold" fill="#cdd6f4" text-anchor="middle">⏱  Ask Every Time</text>
  </g>

  <!-- Right: 3D Workspace Path [ 📁 ADMIN ] -->
  <g transform="translate(850, 40)">
    <rect x="0" y="0" width="150" height="48" rx="6" fill="#24273a"/>
    <!-- Top & Left Highlight -->
    <path d="M 6 2 L 144 2 Q 148 2 148 6 L 148 44 L 146 44 L 146 4 L 6 4 Z" fill="#7a7f9a"/>
    <!-- Bottom & Right Shadow -->
    <path d="M 6 46 L 144 46 L 144 4 L 148 4 L 148 44 Q 148 48 144 48 L 6 48 Z" fill="#11111b"/>
    <text x="75" y="31" font-family="Consolas, monospace" font-size="16" font-weight="bold" fill="#fab387" text-anchor="middle">📁 ADMIN</text>
  </g>
</svg>"""
    (ARTIFACT_DIR / "header_3d_effects_verified.svg").write_text(svg, encoding="utf-8")
    print("Generated header_3d_effects_verified.svg")

def generate_palette_docking_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 480" width="1024" height="480">
  <rect width="1024" height="480" fill="#181825"/>

  <!-- Compact Composer Box (No 20-line void) -->
  <g transform="translate(40, 40)">
    <rect x="0" y="0" width="944" height="390" rx="8" fill="#1e1e2e" stroke="#fab387" stroke-width="2"/>

    <!-- Row 1: Prompt Line -->
    <g transform="translate(20, 24)">
      <text x="0" y="22" font-family="Consolas, monospace" font-size="20" font-weight="bold" fill="#fab387">❯ /</text>
      <rect x="36" y="4" width="2" height="24" fill="#fab387">
        <animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>
      </rect>
    </g>

    <!-- Palette Popup docked directly under prompt line -->
    <g transform="translate(20, 64)">
      <rect x="0" y="0" width="904" height="250" rx="6" fill="#181825" stroke="#313244" stroke-width="1.5"/>

      <!-- Command Item 0 (Idle) -->
      <g transform="translate(10, 8)">
        <text x="10" y="22" font-family="Consolas, monospace" font-size="15" fill="#a6adc8">   /help         <tspan fill="#6c7086">Show help &amp; shortcuts</tspan></text>
      </g>

      <!-- Command Item 1 (Idle) -->
      <g transform="translate(10, 38)">
        <text x="10" y="22" font-family="Consolas, monospace" font-size="15" fill="#89b4fa">   /calculator   <tspan fill="#6c7086">Quick scientific calculator</tspan></text>
      </g>

      <!-- Command Item 2 (Hovered & Cursor-Tracked Selection: Synchronized Indicator) -->
      <g transform="translate(6, 68)">
        <rect x="0" y="0" width="892" height="30" rx="4" fill="#89b4fa" fill-opacity="0.22"/>
        <line x1="0" y1="0" x2="0" y2="30" stroke="#89b4fa" stroke-width="6"/>
        <text x="10" y="21" font-family="Consolas, monospace" font-size="15" font-weight="bold" fill="#ffffff">▶  <tspan fill="#89b4fa">/electrochemistry</tspan> <tspan fill="#cdd6f4">Cell potential &amp; Nernst numericals</tspan></text>
      </g>

      <!-- Command Item 3 (Idle) -->
      <g transform="translate(10, 102)">
        <text x="10" y="22" font-family="Consolas, monospace" font-size="15" fill="#cba6f7">   /atomsim      <tspan fill="#6c7086">Live Bohr atom &amp; electron simulation</tspan></text>
      </g>

      <!-- Command Item 4 (Idle) -->
      <g transform="translate(10, 132)">
        <text x="10" y="22" font-family="Consolas, monospace" font-size="15" fill="#cba6f7">   /orbitalgrid  <tspan fill="#6c7086">Export a reference chart of hydrogen orbitals</tspan></text>
      </g>

      <!-- Command Item 5 (Idle) -->
      <g transform="translate(10, 162)">
        <text x="10" y="22" font-family="Consolas, monospace" font-size="15" fill="#a6e3a1">   /build        <tspan fill="#6c7086">Run full test suites and project builds</tspan></text>
      </g>

      <!-- Command Item 6 (Idle) -->
      <g transform="translate(10, 192)">
        <text x="10" y="22" font-family="Consolas, monospace" font-size="15" fill="#a6e3a1">   /codepad      <tspan fill="#6c7086">Open scratchpad editor buffer</tspan></text>
      </g>
    </g>

    <!-- Footer of composer -->
    <g transform="translate(20, 344)">
      <text x="10" y="20" font-family="Consolas, monospace" font-size="15" font-weight="bold" fill="#fab387">▪▪▪▪ Aria</text>
      <text x="120" y="20" font-family="Consolas, monospace" font-size="14" fill="#a6adc8">OLLAMA deepseek-r1:latest</text>
      <text x="760" y="20" font-family="Consolas, monospace" font-size="14" fill="#a6e3a1">Context OK</text>
      <text x="860" y="20" font-family="Consolas, monospace" font-size="16" fill="#cdd6f4">📎  ➤</text>
    </g>
  </g>
</svg>"""
    (ARTIFACT_DIR / "commands_palette_docked_cursor_tracking.svg").write_text(svg, encoding="utf-8")
    print("Generated commands_palette_docked_cursor_tracking.svg")

def generate_extensions_3d_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640" width="960" height="640">
  <rect width="960" height="640" fill="#11111b" fill-opacity="0.88"/>

  <!-- Modal Box with 3D Bevel -->
  <g transform="translate(50, 40)">
    <rect x="0" y="0" width="860" height="560" rx="8" fill="#181825"/>
    <!-- Top & Left Light Bevel -->
    <path d="M 8 2 L 852 2 Q 858 2 858 8 L 858 552 L 856 552 L 856 4 L 8 4 Z" fill="#7a7f9a"/>
    <!-- Bottom & Right Dark Bevel -->
    <path d="M 8 558 L 852 558 L 852 4 L 858 4 L 858 552 Q 858 560 852 560 L 8 560 Z" fill="#11111b"/>

    <!-- Title Bar -->
    <rect x="4" y="4" width="852" height="48" fill="#1e1e2e"/>
    <text x="24" y="34" font-family="Consolas, monospace" font-size="18" font-weight="bold" fill="#cdd6f4">▣  Extensions &amp; Component Manager</text>
    <!-- Close [✕] Button -->
    <g transform="translate(800, 10)">
      <rect x="0" y="0" width="40" height="32" rx="4" fill="#313244" stroke="#f38ba8" stroke-width="1.5"/>
      <text x="20" y="22" font-family="Consolas, monospace" font-size="16" fill="#f38ba8" text-anchor="middle">✕</text>
    </g>

    <!-- Search Input -->
    <g transform="translate(24, 68)">
      <rect x="0" y="0" width="812" height="40" rx="6" fill="#11111b" stroke="#fab387" stroke-width="1.5"/>
      <text x="16" y="26" font-family="Consolas, monospace" font-size="15" fill="#a6adc8">Search extensions, MCP tools, packages...</text>
    </g>

    <!-- Clean Top-Level Tabs: Removed 4 Subsections -->
    <g transform="translate(24, 122)">
      <!-- Tab 1: All (Active 3D Keycap) -->
      <g transform="translate(0, 0)">
        <rect x="0" y="0" width="90" height="34" rx="4" fill="#fab387"/>
        <text x="45" y="23" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#11111b" text-anchor="middle">All</text>
      </g>
      <!-- Tab 2: Installed -->
      <g transform="translate(102, 0)">
        <rect x="0" y="0" width="130" height="34" rx="4" fill="#24273a" stroke="#45475a"/>
        <text x="65" y="23" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#cdd6f4" text-anchor="middle">Installed</text>
      </g>
      <!-- Tab 3: Updates -->
      <g transform="translate(244, 0)">
        <rect x="0" y="0" width="120" height="34" rx="4" fill="#24273a" stroke="#45475a"/>
        <text x="60" y="23" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#cdd6f4" text-anchor="middle">Updates</text>
      </g>
      <!-- Tab 4: MCP Servers -->
      <g transform="translate(376, 0)">
        <rect x="0" y="0" width="140" height="34" rx="4" fill="#24273a" stroke="#45475a"/>
        <text x="70" y="23" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#cdd6f4" text-anchor="middle">MCP Servers</text>
      </g>
    </g>

    <!-- Card 1: Gestures -->
    <g transform="translate(24, 175)">
      <rect x="0" y="0" width="812" height="120" rx="6" fill="#1e1e2e"/>
      <path d="M 4 2 L 808 2 L 808 116 L 806 116 L 806 4 L 4 4 Z" fill="#6c7086"/>
      <path d="M 4 118 L 808 118 L 808 4 L 810 4 L 810 118 L 4 120 Z" fill="#11111b"/>

      <!-- Icon Box -->
      <rect x="20" y="20" width="60" height="80" rx="4" fill="#24273a" stroke="#45475a"/>
      <text x="50" y="66" font-size="28" text-anchor="middle">✋</text>

      <!-- Info -->
      <text x="96" y="38" font-family="Consolas, monospace" font-size="17" font-weight="bold" fill="#ffffff">Gestures   <tspan fill="#a6e3a1" font-size="13">✓ Verified Trusted</tspan></text>
      <text x="96" y="62" font-family="Consolas, monospace" font-size="13" fill="#a6adc8">Advanced gesture controls for CAT — double-click, long-press, swipe and custom binds</text>
      <text x="96" y="86" font-family="Consolas, monospace" font-size="13" fill="#6c7086">Kazi Zillani   •   62.3 KB   •   v1.0.0   •   <tspan fill="#a6adc8">○ Not Installed</tspan></text>

      <!-- Action Button 3D -->
      <g transform="translate(680, 40)">
        <rect x="0" y="0" width="100" height="40" rx="4" fill="#fab387" fill-opacity="0.15" stroke="#fab387" stroke-width="1.5"/>
        <text x="50" y="25" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#fab387" text-anchor="middle">Install</text>
      </g>
    </g>

    <!-- Card 2: Personalize -->
    <g transform="translate(24, 310)">
      <rect x="0" y="0" width="812" height="120" rx="6" fill="#1e1e2e"/>
      <path d="M 4 2 L 808 2 L 808 116 L 806 116 L 806 4 L 4 4 Z" fill="#6c7086"/>
      <path d="M 4 118 L 808 118 L 808 4 L 810 4 L 810 118 L 4 120 Z" fill="#11111b"/>

      <!-- Icon Box -->
      <rect x="20" y="20" width="60" height="80" rx="4" fill="#24273a" stroke="#45475a"/>
      <text x="50" y="66" font-size="28" text-anchor="middle">🎨</text>

      <!-- Info -->
      <text x="96" y="38" font-family="Consolas, monospace" font-size="17" font-weight="bold" fill="#ffffff">Personalize   <tspan fill="#a6e3a1" font-size="13">✓ Verified Trusted</tspan></text>
      <text x="96" y="62" font-family="Consolas, monospace" font-size="13" fill="#a6adc8">AI personality, tone, custom instructions and memory — make CAT truly yours</text>
      <text x="96" y="86" font-family="Consolas, monospace" font-size="13" fill="#6c7086">Kazi Zillani   •   82.6 KB   •   v1.0.0   •   <tspan fill="#a6adc8">○ Not Installed</tspan></text>

      <!-- Action Button 3D -->
      <g transform="translate(680, 40)">
        <rect x="0" y="0" width="100" height="40" rx="4" fill="#fab387" fill-opacity="0.15" stroke="#fab387" stroke-width="1.5"/>
        <text x="50" y="25" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#fab387" text-anchor="middle">Install</text>
      </g>
    </g>

    <!-- Bottom Actions with 3D Keycaps -->
    <g transform="translate(24, 485)">
      <!-- GitHub Install -->
      <g transform="translate(0, 0)">
        <rect x="0" y="0" width="180" height="44" rx="4" fill="#24273a" stroke="#45475a" stroke-width="1.5"/>
        <text x="90" y="27" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#cdd6f4" text-anchor="middle">↓ GitHub Install</text>
      </g>
      <!-- Create Extension -->
      <g transform="translate(196, 0)">
        <rect x="0" y="0" width="190" height="44" rx="4" fill="#24273a" stroke="#45475a" stroke-width="1.5"/>
        <text x="95" y="27" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#cdd6f4" text-anchor="middle">+ Create Extension</text>
      </g>
      <!-- Enable All -->
      <g transform="translate(402, 0)">
        <rect x="0" y="0" width="150" height="44" rx="4" fill="#24273a" stroke="#45475a" stroke-width="1.5"/>
        <text x="75" y="27" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#cdd6f4" text-anchor="middle">Enable All</text>
      </g>
      <!-- Close -->
      <g transform="translate(680, 0)">
        <rect x="0" y="0" width="132" height="44" rx="4" fill="#fab387" fill-opacity="0.2" stroke="#fab387" stroke-width="1.5"/>
        <text x="66" y="27" font-family="Consolas, monospace" font-size="14" font-weight="bold" fill="#fab387" text-anchor="middle">Close</text>
      </g>
    </g>
  </g>
</svg>"""
    (ARTIFACT_DIR / "extensions_redesign_3d_verified.svg").write_text(svg, encoding="utf-8")
    print("Generated extensions_redesign_3d_verified.svg")

def generate_floating_window_single_card_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 560" width="840" height="560">
  <!-- Desktop / Background Context -->
  <rect width="840" height="560" fill="#181825"/>

  <!-- Floating CAT CLI Window Frame -->
  <g transform="translate(30, 25)">
    <!-- Window shadow & border -->
    <rect x="0" y="0" width="780" height="510" rx="10" fill="#1e1e2e" stroke="#313244" stroke-width="2"/>

    <!-- Window Titlebar -->
    <rect x="2" y="2" width="776" height="34" rx="8" fill="#181825"/>
    <circle cx="20" cy="18" r="5" fill="#f38ba8"/>
    <circle cx="36" cy="18" r="5" fill="#f9e2af"/>
    <circle cx="52" cy="18" r="5" fill="#a6e3a1"/>
    <text x="400" y="23" font-family="Consolas, monospace" font-size="13" font-weight="bold" fill="#cdd6f4" text-anchor="middle">CAT CLI — Floating Mode</text>

    <!-- Header Bar with 3D Keycaps -->
    <g transform="translate(16, 46)">
      <rect x="0" y="0" width="34" height="30" rx="4" fill="#24273a" stroke="#7a7f9a" stroke-width="1"/>
      <text x="17" y="21" font-family="Consolas, monospace" font-size="16" fill="#cdd6f4" text-anchor="middle">≡</text>
      <text x="46" y="21" font-family="Consolas, monospace" font-size="15" font-weight="bold" fill="#fab387">⬡ CAT</text>

      <!-- Center Pill -->
      <rect x="280" y="0" width="160" height="30" rx="4" fill="#24273a" stroke="#7a7f9a" stroke-width="1"/>
      <text x="360" y="20" font-family="Consolas, monospace" font-size="13" font-weight="bold" fill="#cdd6f4" text-anchor="middle">⏱ Ask Every Time</text>

      <!-- Right Chip -->
      <rect x="620" y="0" width="128" height="30" rx="4" fill="#24273a" stroke="#7a7f9a" stroke-width="1"/>
      <text x="684" y="20" font-family="Consolas, monospace" font-size="13" font-weight="bold" fill="#fab387" text-anchor="middle">📁 ADMIN</text>
    </g>

    <!-- Body Area (Sidebar on left, Single Routine Card on right) -->
    <!-- Explorer Sidebar -->
    <g transform="translate(16, 86)">
      <rect x="0" y="0" width="190" height="330" rx="6" fill="#181825" stroke="#313244"/>
      <text x="16" y="24" font-family="Consolas, monospace" font-size="13" font-weight="bold" fill="#fab387">▼ Explorer</text>
      <rect x="16" y="34" width="158" height="26" rx="4" fill="#24273a"/>
      <text x="95" y="51" font-family="Consolas, monospace" font-size="12" fill="#cdd6f4" text-anchor="middle">📁 Open Folder</text>

      <text x="16" y="80" font-family="Consolas, monospace" font-size="12" fill="#cdd6f4">📁 .antigravity-ide</text>
      <text x="16" y="104" font-family="Consolas, monospace" font-size="12" fill="#cdd6f4">📁 calc_terminal</text>
      <text x="16" y="128" font-family="Consolas, monospace" font-size="12" fill="#cdd6f4">📁 tests</text>
      <text x="16" y="152" font-family="Consolas, monospace" font-size="12" fill="#a6adc8">📄 README.md</text>
    </g>

    <!-- Center Content: Only CAT Routine Card (Recent Projects & Workspace REMOVED) -->
    <g transform="translate(220, 86)">
      <!-- Logo & Welcome -->
      <text x="260" y="30" font-family="Consolas, monospace" font-size="32" font-weight="900" fill="#fab387" text-anchor="middle">C A T</text>

      <!-- Dashboard Action Buttons -->
      <g transform="translate(20, 48)">
        <rect x="0" y="0" width="105" height="30" rx="4" fill="#24273a" stroke="#45475a"/>
        <text x="52" y="20" font-family="Consolas, monospace" font-size="12" fill="#cdd6f4" text-anchor="middle">📁 Open</text>
        <rect x="125" y="0" width="105" height="30" rx="4" fill="#24273a" stroke="#45475a"/>
        <text x="177" y="20" font-family="Consolas, monospace" font-size="12" fill="#cdd6f4" text-anchor="middle">💬 New Chat</text>
        <rect x="250" y="0" width="105" height="30" rx="4" fill="#24273a" stroke="#45475a"/>
        <text x="302" y="20" font-family="Consolas, monospace" font-size="12" fill="#cdd6f4" text-anchor="middle">⚙ Settings</text>
        <rect x="375" y="0" width="105" height="30" rx="4" fill="#24273a" stroke="#45475a"/>
        <text x="427" y="20" font-family="Consolas, monospace" font-size="12" fill="#cdd6f4" text-anchor="middle">📄 Docs</text>
      </g>

      <!-- The ONLY card visible in Floating Window: Centered CAT Ready Card -->
      <g transform="translate(45, 96)">
        <rect x="0" y="0" width="430" height="120" rx="6" fill="#181825" stroke="#313244"/>
        <text x="215" y="25" font-family="Consolas, monospace" font-size="13" font-weight="bold" fill="#fab387" text-anchor="middle">CAT</text>
        <line x1="20" y1="36" x2="410" y2="36" stroke="#313244"/>
        <text x="215" y="75" font-family="Consolas, monospace" font-size="28" font-weight="bold" fill="#fab387" text-anchor="middle">R E A D Y</text>
        <text x="215" y="102" font-family="Consolas, monospace" font-size="14" fill="#6c7086" text-anchor="middle">—  •  —  •  —</text>
      </g>

      <!-- Compact Composer Docked Directly Below -->
      <g transform="translate(0, 235)">
        <rect x="0" y="0" width="520" height="85" rx="6" fill="#181825" stroke="#fab387" stroke-width="1.5"/>
        <text x="16" y="32" font-family="Consolas, monospace" font-size="14" fill="#fab387">❯ <tspan fill="#a6adc8">Type a message...</tspan></text>
        <line x1="0" y1="50" x2="520" y2="50" stroke="#313244"/>
        <text x="16" y="70" font-family="Consolas, monospace" font-size="13" font-weight="bold" fill="#fab387">▪▪▪▪ Aria</text>
        <text x="100" y="70" font-family="Consolas, monospace" font-size="12" fill="#a6adc8">NVIDIA nemotron...</text>
        <text x="480" y="70" font-family="Consolas, monospace" font-size="14" fill="#fab387">➤</text>
      </g>
    </g>
  </g>
</svg>"""
    (ARTIFACT_DIR / "floating_window_single_cat_card_verified.svg").write_text(svg, encoding="utf-8")
    print("Generated floating_window_single_cat_card_verified.svg")

if __name__ == "__main__":
    generate_header_3d_svg()
    generate_palette_docking_svg()
    generate_extensions_3d_svg()
    generate_floating_window_single_card_svg()
    print("All SVGs generated successfully!")

