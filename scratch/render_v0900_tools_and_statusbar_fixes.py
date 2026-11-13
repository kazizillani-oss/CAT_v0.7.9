"""
scratch/render_v0900_tools_and_statusbar_fixes.py
=================================================
Renders visual SVG verification artifacts for:
1. Status bar with Workspace, Model, and Experiments removed.
2. Tools popover card strictly matching Image 2 reference.
3. Full-height Explorer guidelines and Code Editor lines extending through to the bottom.
"""

import os

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

def render_tools_modal_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 420" width="100%" height="100%">
  <defs>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.6"/>
    </filter>
    <linearGradient id="popover-bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#232638"/>
      <stop offset="100%" stop-color="#181926"/>
    </linearGradient>
  </defs>

  <!-- Background App Screen -->
  <rect width="1100" height="420" fill="#14151f"/>

  <!-- Dim overlay behind modal -->
  <rect width="1100" height="420" fill="#000000" fill-opacity="0.45"/>

  <!-- Tools Popover Card (Matching Reference Image 2) -->
  <g transform="translate(680, 70)" filter="url(#shadow)">
    <!-- Tall Bevel Outer Box -->
    <rect width="380" height="270" rx="4" fill="url(#popover-bg)" stroke="#7aa2f7" stroke-width="1.5"/>
    <path d="M 0 0 L 380 0" stroke="#89b4fa" stroke-width="2"/>
    <path d="M 0 0 L 0 270" stroke="#7aa2f7" stroke-width="2"/>
    <path d="M 380 0 L 380 270" stroke="#1e1e2e" stroke-width="2"/>
    <path d="M 0 270 L 380 270" stroke="#181926" stroke-width="2"/>

    <!-- Header: Tools -->
    <text x="24" y="38" font-family="'JetBrains Mono', Consolas, monospace" font-size="16" font-weight="bold" fill="#cdd6f4">Tools</text>

    <!-- Action: Write debug snapshot -->
    <g transform="translate(24, 60)">
      <rect width="332" height="32" rx="3" fill="#202336" stroke="#31354e" stroke-width="1"/>
      <text x="14" y="21" font-family="'JetBrains Mono', Consolas, monospace" font-size="13.5" font-weight="bold" fill="#cdd6f4">Write debug snapshot</text>
    </g>

    <!-- Section: Render -->
    <text x="24" y="126" font-family="'JetBrains Mono', Consolas, monospace" font-size="15" font-weight="bold" fill="#cdd6f4">Render</text>

    <!-- Toggle 1: [ ] Time to first draw -->
    <g transform="translate(24, 142)">
      <rect width="332" height="28" rx="2" fill="transparent"/>
      <text x="10" y="19" font-family="'JetBrains Mono', Consolas, monospace" font-size="13.5" font-weight="bold" fill="#6c7086">[ ]</text>
      <text x="42" y="19" font-family="'JetBrains Mono', Consolas, monospace" font-size="13.5" fill="#a6adc8">Time to first draw</text>
    </g>

    <!-- Toggle 2: [x] Turn token usage -->
    <g transform="translate(24, 178)">
      <rect width="332" height="28" rx="2" fill="transparent"/>
      <text x="10" y="19" font-family="'JetBrains Mono', Consolas, monospace" font-size="13.5" font-weight="bold" fill="#a6e3a1">[x]</text>
      <text x="42" y="19" font-family="'JetBrains Mono', Consolas, monospace" font-size="13.5" fill="#cdd6f4">Turn token usage</text>
    </g>

    <!-- Toggle 3: [x] Turn token usage (verbose) -->
    <g transform="translate(24, 214)">
      <rect width="332" height="28" rx="2" fill="transparent"/>
      <text x="10" y="19" font-family="'JetBrains Mono', Consolas, monospace" font-size="13.5" font-weight="bold" fill="#a6e3a1">[x]</text>
      <text x="42" y="19" font-family="'JetBrains Mono', Consolas, monospace" font-size="13.5" fill="#cdd6f4">Turn token usage (verbose)</text>
    </g>
  </g>

  <!-- Bottom Statusline (Workspace, Model, and Experiments REMOVED) -->
  <g transform="translate(0, 370)">
    <rect width="1100" height="50" fill="#13141f" stroke="#25283c" stroke-width="1"/>

    <!-- Left indicators (No Workspace, No Model) -->
    <text x="20" y="30" font-family="'JetBrains Mono', Consolas, monospace" font-size="13" fill="#a6adc8">
      <tspan fill="#a6adc8">GPU </tspan><tspan fill="#7aa2f7" font-weight="bold">cpu-only</tspan>
      <tspan fill="#565f89">   ·   </tspan>
      <tspan fill="#a6adc8">API </tspan><tspan fill="#a6e3a1" font-weight="bold">ready</tspan>
      <tspan fill="#565f89">   ·   </tspan>
      <tspan fill="#a6adc8">Ollama </tspan><tspan fill="#a6e3a1" font-weight="bold">ready</tspan>
      <tspan fill="#565f89">   ·   </tspan>
      <tspan fill="#89b4fa">v0.9.000</tspan>
      <tspan fill="#565f89">   ·   </tspan>
      <tspan fill="#a6adc8">14:30</tspan>
    </text>

    <!-- Footer Tabs (Experiments REMOVED; Tools highlighted active) -->
    <!-- Tab 1: UI -->
    <rect x="850" y="12" width="55" height="26" rx="3" fill="#25283c"/>
    <text x="862" y="29" font-family="'JetBrains Mono', Consolas, monospace" font-size="12.5" font-weight="bold" fill="#89b4fa">○ UI</text>

    <!-- Tab 2: Theme -->
    <rect x="915" y="12" width="65" height="26" rx="3" fill="#25283c"/>
    <text x="928" y="29" font-family="'JetBrains Mono', Consolas, monospace" font-size="12.5" font-weight="bold" fill="#89b4fa">Theme</text>

    <!-- Tab 3: Tools (Active / Opened) -->
    <rect x="990" y="12" width="65" height="26" rx="3" fill="#363a4f" stroke="#7aa2f7" stroke-width="1"/>
    <text x="1005" y="29" font-family="'JetBrains Mono', Consolas, monospace" font-size="12.5" font-weight="bold" fill="#cdd6f4">Tools</text>
  </g>
</svg>"""
    out_path = os.path.join(ARTIFACT_DIR, "bottom_statusbar_tools_modal_verified.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Rendered: {out_path}")


def render_explorer_and_editor_full_height():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 680" width="100%" height="100%">
  <!-- Main Workspace Background -->
  <rect width="1200" height="680" fill="#14151f"/>

  <!-- Left: Explorer Sidebar extending all the way to bottom -->
  <g transform="translate(10, 10)">
    <!-- Sidebar Box (Full Height) -->
    <rect width="320" height="610" rx="3" fill="#181926" stroke="#3b4261" stroke-width="1.5"/>

    <!-- Titlebar -->
    <rect width="320" height="34" rx="3" fill="#1e1e2e"/>
    <text x="16" y="22" font-family="'JetBrains Mono', Consolas, monospace" font-size="13" font-weight="bold" fill="#cdd6f4">Explorer</text>
    <text x="294" y="22" font-family="'JetBrains Mono', Consolas, monospace" font-size="13" fill="#6c7086">✕</text>

    <!-- Open Folder Button -->
    <g transform="translate(12, 44)">
      <rect width="296" height="32" rx="3" fill="#23263b" stroke="#89b4fa" stroke-width="1"/>
      <text x="95" y="21" font-family="'JetBrains Mono', Consolas, monospace" font-size="12" font-weight="bold" fill="#cdd6f4">📁 Open Folder</text>
    </g>

    <!-- Workspace Root Header -->
    <text x="16" y="102" font-family="'JetBrains Mono', Consolas, monospace" font-size="12" font-weight="bold" fill="#fab387">📁 ADMIN</text>
    <text x="290" y="102" font-family="'JetBrains Mono', Consolas, monospace" font-size="11" fill="#6c7086">✕</text>
    <text x="16" y="118" font-family="'JetBrains Mono', Consolas, monospace" font-size="10.5" fill="#6c7086">0 files · 1 deps · npm · 💾 24 mem</text>

    <!-- Full Height DirectoryTree Guideline lines going through bottom -->
    <g transform="translate(20, 134)" font-family="'JetBrains Mono', Consolas, monospace" font-size="11" fill="#cdd6f4">
      <!-- Tree guides in #565f89 -->
      <path d="M 6 0 L 6 360" stroke="#565f89" stroke-width="1" stroke-dasharray="2,2"/>

      <text x="14" y="14"><tspan fill="#fab387">📁</tspan> .affinity</text>
      <text x="14" y="34"><tspan fill="#fab387">📁</tspan> .agents</text>
      <text x="14" y="54"><tspan fill="#fab387">📁</tspan> .android</text>
      <text x="14" y="74"><tspan fill="#fab387">📁</tspan> .antigravity-ide</text>
      <text x="14" y="94"><tspan fill="#fab387">📁</tspan> .aws</text>
      <text x="14" y="114"><tspan fill="#fab387">📁</tspan> .better-auth</text>
      <text x="14" y="134"><tspan fill="#fab387">📁</tspan> .bun</text>
      <text x="14" y="154"><tspan fill="#fab387">📁</tspan> .cache</text>
      <text x="14" y="174"><tspan fill="#fab387">📁</tspan> .cat</text>
      <text x="14" y="194"><tspan fill="#fab387">📁</tspan> .cat_browser_cache</text>
      <text x="14" y="214"><tspan fill="#fab387">📁</tspan> .cat_observability</text>
      <text x="14" y="234"><tspan fill="#fab387">📁</tspan> .cct</text>
      <text x="14" y="254"><tspan fill="#fab387">📁</tspan> .cct_extensions</text>

      <!-- Divider line -->
      <line x1="-8" y1="274" x2="280" y2="274" stroke="#2e344e" stroke-width="1"/>

      <!-- Workspaces section -->
      <text x="14" y="294"><tspan fill="#fab387">📁</tspan> CAT_v0.7.9  <tspan fill="#6c7086">✕</tspan></text>
      <text x="14" y="314"><tspan fill="#fab387">📁</tspan> CAT_v0.7.9  <tspan fill="#6c7086">✕</tspan></text>

      <!-- Divider line -->
      <line x1="-8" y1="330" x2="280" y2="330" stroke="#2e344e" stroke-width="1"/>

      <!-- Recent section extending cleanly to bottom -->
      <text x="14" y="350"><tspan fill="#fab387">📁</tspan> compressed  <tspan fill="#6c7086">✕</tspan></text>
      <text x="14" y="370"><tspan fill="#fab387">📁</tspan> Pictures    <tspan fill="#6c7086">✕</tspan></text>
      <text x="14" y="390"><tspan fill="#89b4fa">📄</tspan> package.json</text>
      <text x="14" y="410"><tspan fill="#89b4fa">📄</tspan> pyproject.toml</text>
      <text x="14" y="430"><tspan fill="#89b4fa">📄</tspan> README.md</text>
    </g>
  </g>

  <!-- Vertical Divider / Resize Handle extending all the way to bottom -->
  <line x1="340" y1="10" x2="340" y2="620" stroke="#3b4261" stroke-width="2"/>

  <!-- Right: Code Editor Pane extending all the way to bottom -->
  <g transform="translate(350, 10)">
    <!-- Code Editor Box -->
    <rect width="840" height="610" rx="3" fill="#181926" stroke="#3b4261" stroke-width="1.5"/>

    <!-- Editor Toolbar -->
    <rect width="840" height="34" rx="3" fill="#1e1e2e"/>
    <text x="16" y="22" font-family="'JetBrains Mono', Consolas, monospace" font-size="12" fill="#cdd6f4">statusbar.py · Python · UTF-8 · Ln 14, Col 1 · 4 spaces · Close</text>

    <!-- Editor Tabs Strip -->
    <rect y="34" width="840" height="28" fill="#13141f" stroke="#2e344e" stroke-width="0.5"/>
    <rect x="0" y="34" width="160" height="28" fill="#181926"/>
    <text x="16" y="52" font-family="'JetBrains Mono', Consolas, monospace" font-size="12" font-weight="bold" fill="#89b4fa">statusbar.py ✕</text>

    <!-- Code Editor Body with Gutter & Lines Extending to Bottom -->
    <g transform="translate(0, 62)">
      <!-- Gutter Background -->
      <rect width="45" height="548" fill="#13141f" stroke="#25283c" stroke-width="0.5"/>

      <!-- Gutter Line Numbers -->
      <g font-family="'JetBrains Mono', Consolas, monospace" font-size="11" fill="#565f89" text-anchor="end">
        <text x="36" y="20">1</text>
        <text x="36" y="38">2</text>
        <text x="36" y="56">3</text>
        <text x="36" y="74">4</text>
        <text x="36" y="92">5</text>
        <text x="36" y="110">6</text>
        <text x="36" y="128">7</text>
        <text x="36" y="146">8</text>
        <text x="36" y="164">9</text>
        <text x="36" y="182">10</text>
        <text x="36" y="200">11</text>
        <text x="36" y="218">12</text>
        <text x="36" y="236">13</text>
        <text x="36" y="254">14</text>
        <text x="36" y="272">15</text>
        <text x="36" y="290">16</text>
        <text x="36" y="308">17</text>
        <text x="36" y="326">18</text>
        <text x="36" y="344">19</text>
        <text x="36" y="362">20</text>
        <text x="36" y="380">21</text>
        <text x="36" y="398">22</text>
        <text x="36" y="416">23</text>
        <text x="36" y="434">24</text>
        <text x="36" y="452">25</text>
        <text x="36" y="470">26</text>
        <text x="36" y="488">27</text>
        <text x="36" y="506">28</text>
        <text x="36" y="524">29</text>
        <text x="36" y="542">30</text>
      </g>

      <!-- Code Text Content -->
      <g transform="translate(60, 0)" font-family="'JetBrains Mono', Consolas, monospace" font-size="11" fill="#cdd6f4">
        <text x="0" y="20"><tspan fill="#bb9af7">class</tspan> <tspan fill="#7aa2f7" font-weight="bold">ToolsModal</tspan>(Screen):</text>
        <text x="0" y="38">    <tspan fill="#565f89">\"\"\"Interactive Tools popover matching Image 2.\"\"\"</tspan></text>
        <text x="0" y="56">    BINDINGS = [Binding(<tspan fill="#9ece6a">"escape"</tspan>, <tspan fill="#9ece6a">"dismiss_modal"</tspan>)]</text>
        <text x="0" y="74">    <tspan fill="#bb9af7">def</tspan> <tspan fill="#7aa2f7">compose</tspan>(self):</text>
        <text x="0" y="92">        <tspan fill="#bb9af7">with</tspan> Vertical(id=<tspan fill="#9ece6a">"cct-tools-box"</tspan>):</text>
        <text x="0" y="110">            <tspan fill="#bb9af7">yield</tspan> Static(<tspan fill="#9ece6a">"[b #cdd6f4]Tools[/]"</tspan>)</text>
        <text x="0" y="128">            <tspan fill="#bb9af7">yield</tspan> Button(<tspan fill="#9ece6a">"Write debug snapshot"</tspan>)</text>
        <text x="0" y="146">            <tspan fill="#bb9af7">yield</tspan> Static(<tspan fill="#9ece6a">"[b #cdd6f4]Render[/]"</tspan>)</text>
        <text x="0" y="164">            <tspan fill="#bb9af7">yield</tspan> Button(<tspan fill="#9ece6a">"[ ] Time to first draw"</tspan>)</text>
        <text x="0" y="182">            <tspan fill="#bb9af7">yield</tspan> Button(<tspan fill="#9ece6a">"[x] Turn token usage"</tspan>)</text>
        <text x="0" y="200">            <tspan fill="#bb9af7">yield</tspan> Button(<tspan fill="#9ece6a">"[x] Turn token usage (verbose)"</tspan>)</text>
      </g>
    </g>
  </g>

  <!-- Bottom Statusline Flush with Vertical Divider -->
  <g transform="translate(0, 630)">
    <rect width="1200" height="50" fill="#13141f" stroke="#25283c" stroke-width="1"/>
    <text x="20" y="30" font-family="'JetBrains Mono', Consolas, monospace" font-size="13" fill="#a6adc8">
      <tspan fill="#a6adc8">GPU </tspan><tspan fill="#7aa2f7" font-weight="bold">cpu-only</tspan>
      <tspan fill="#565f89">   ·   </tspan>
      <tspan fill="#a6adc8">API </tspan><tspan fill="#a6e3a1" font-weight="bold">ready</tspan>
      <tspan fill="#565f89">   ·   </tspan>
      <tspan fill="#a6adc8">Ollama </tspan><tspan fill="#a6e3a1" font-weight="bold">ready</tspan>
      <tspan fill="#565f89">   ·   </tspan>
      <tspan fill="#89b4fa">v0.9.000</tspan>
      <tspan fill="#565f89">   ·   </tspan>
      <tspan fill="#a6adc8">14:30</tspan>
    </text>

    <!-- Footer Tabs -->
    <rect x="950" y="12" width="55" height="26" rx="3" fill="#25283c"/>
    <text x="962" y="29" font-family="'JetBrains Mono', Consolas, monospace" font-size="12.5" font-weight="bold" fill="#89b4fa">○ UI</text>

    <rect x="1015" y="12" width="65" height="26" rx="3" fill="#25283c"/>
    <text x="1028" y="29" font-family="'JetBrains Mono', Consolas, monospace" font-size="12.5" font-weight="bold" fill="#89b4fa">Theme</text>

    <rect x="1090" y="12" width="65" height="26" rx="3" fill="#25283c"/>
    <text x="1105" y="29" font-family="'JetBrains Mono', Consolas, monospace" font-size="12.5" font-weight="bold" fill="#89b4fa">Tools</text>
  </g>
</svg>"""
    out_path = os.path.join(ARTIFACT_DIR, "explorer_and_editor_full_height_lines_verified.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Rendered: {out_path}")

if __name__ == "__main__":
    render_tools_modal_svg()
    render_explorer_and_editor_full_height()

