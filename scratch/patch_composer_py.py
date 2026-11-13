# scratch/patch_composer_py.py
import re

composer_path = 'calc_terminal/ui/composer.py'
with open(composer_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update StickyComposer.compose()
old_comp_compose = re.compile(
    r'def compose\(self\):.*?yield Static\(id="cct-context-spacer"\)\s*yield Static\(\"\[bold #a6e3a1\]● Ready\[/\]\", id=\"badge-status\", classes=\"cct-context-status\"\)',
    re.DOTALL
)

new_comp_compose = '''def compose(self):
            prov, mdl = self._get_provider_and_model()
            clean_mdl = mdl
            for prefix in ("OLLAMA ", "OPENROUTER ", "OPENAI ", "GEMINI ", "ANTHROPIC ", "GROQ "):
                if clean_mdl.upper().startswith(prefix):
                    clean_mdl = clean_mdl[len(prefix):]
                    break
            with Horizontal(id="cct-composer-context-bar"):
                with Horizontal(id="cct-context-left"):
                    yield _Badge(self._mode_badge_markup(self.notebook_mode),
                                 "badge-notebook", self._toggle_notebook)
                    yield Static("·", classes="cct-badge-sep")
                    yield _Badge(f"[{prov or 'AI'}]", "badge-provider", self._open_model)
                    yield Static("·", classes="cct-badge-sep")
                    yield _Badge(clean_mdl or "Model unavailable", "badge-model-top", self._open_model)
                yield Static(id="cct-context-spacer")
                yield Static("[bold #a6e3a1]● Ready[/]", id="badge-status", classes="cct-context-status")'''

if old_comp_compose.search(content):
    content = old_comp_compose.sub(new_comp_compose, content)
    print("Patched composer.py StickyComposer.compose top context bar")
else:
    print("Warning: old_comp_compose did not match")

# 2. Update _update_context_bar
old_update_context = re.compile(
    r'def _update_context_bar\(self\):.*?self\.query_one\(ComposerFooter\)\.set_provider_model\(.*?pass',
    re.DOTALL
)

new_update_context = '''def _update_context_bar(self):
            try:
                self.query_one("#badge-notebook", _Badge).update(
                    self._mode_badge_markup(self.notebook_mode)
                )
            except Exception:
                pass
            try:
                prov, mdl = self._get_provider_and_model()
                clean_mdl = mdl
                for prefix in ("OLLAMA ", "OPENROUTER ", "OPENAI ", "GEMINI ", "ANTHROPIC ", "GROQ "):
                    if clean_mdl.upper().startswith(prefix):
                        clean_mdl = clean_mdl[len(prefix):]
                        break
                try:
                    self.query_one("#badge-provider", _Badge).update(f"[{prov or 'AI'}]")
                except Exception:
                    pass
                try:
                    self.query_one("#badge-model-top", _Badge).update(clean_mdl or "Model unavailable")
                except Exception:
                    pass
                try:
                    self.query_one(ComposerFooter).set_provider_model(
                        prov, mdl, is_backup=self._backup_override is not None)
                except Exception:
                    pass
            except Exception:
                pass'''

if old_update_context.search(content):
    content = old_update_context.sub(new_update_context, content)
    print("Patched composer.py _update_context_bar")
else:
    print("Warning: old_update_context did not match")

# 3. Add btn-permissions and btn-security to on_button_pressed
old_btn_press = '''            elif bid == "btn-attach":
                try:
                    self.app.action_prompt_attach()
                except Exception:
                    pass'''

new_btn_press = '''            elif bid == "btn-attach":
                try:
                    self.app.action_prompt_attach()
                except Exception:
                    pass
            elif bid == "btn-permissions":
                try:
                    self.app.action_toggle_permissions()
                except Exception:
                    try:
                        from .permission_panel import PermissionsSettingsPanel
                        self.query_one(PermissionsSettingsPanel).toggle_panel()
                    except Exception:
                        pass
            elif bid == "btn-security":
                try:
                    from .. import permissions as perm
                    perm.manager.cycle_mode()
                    self.app.notify(f"Security: {perm.manager.mode_label()}", title="Security Mode")
                except Exception:
                    pass'''

if old_btn_press in content:
    content = content.replace(old_btn_press, new_btn_press)
    print("Patched composer.py on_button_pressed with permissions and security handlers")
else:
    print("Warning: old_btn_press not found")

# 4. Update _apply_compact_height to avoid 2-line idle void
old_apply_height = '''                else:
                    editor.styles.min_height = 2
                    avail = int(self.screen.size.height * 0.6) - 5
                    editor_max = max(2, min(10, avail))
                    editor.styles.max_height = editor_max
                    stack.styles.min_height = 2
                    stack.styles.max_height = editor_max
                    row.styles.min_height = 2'''

new_apply_height = '''                else:
                    line_count = max(1, min(5, editor.text.count("\\n") + 1))
                    editor.styles.min_height = 1
                    avail = int(self.screen.size.height * 0.6) - 5
                    editor_max = max(1, min(10, avail))
                    editor.styles.max_height = editor_max
                    if not getattr(self, "_explicit_height", None):
                        editor.styles.height = line_count
                        stack.styles.height = line_count
                    stack.styles.min_height = 1
                    stack.styles.max_height = editor_max
                    row.styles.min_height = 1
                    row.styles.height = "auto"'''

if old_apply_height in content:
    content = content.replace(old_apply_height, new_apply_height)
    print("Patched composer.py _apply_compact_height to be truly compact (min-height 1)")
else:
    print("Warning: old_apply_height not found")

with open(composer_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated composer.py written.")

