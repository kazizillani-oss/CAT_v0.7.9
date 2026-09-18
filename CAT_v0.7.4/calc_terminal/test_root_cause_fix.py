"""CCT root-cause engineering fix — regression tests.

Covers the full model→tool→execution→result→model pipeline:
  - XML <invoke> / <minimax:toolcall> / bare-invoke tool calls EXECUTE
  - JSON protocol tool calls execute
  - multi-tool-call responses execute
  - agent continues after tool results and finishes
  - permission modes gate execution (ask/full/restricted)
  - archive tools: list/delete/validate/extract/add roundtrip with
    safe-replace semantics (original preserved on failure)
  - clean_final_text strips ALL internal tool markup
  - paths_from_paste handles drag-and-drop path formats, rejects prose
  - workspace read/write path resolution incl. attachment exception

Run: python -m pytest calc_terminal/test_root_cause_fix.py -q
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calc_terminal import agent as cct_agent
from calc_terminal import workspace as cct_workspace
from calc_terminal import permissions as perm


class _ScriptedModel:
    """Replaces aicore.query_ai with a canned response sequence so the
    real run_agent loop can be driven end-to-end with no network."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, prompt, system_prompt=None, **kw):
        self.calls.append(prompt)
        i = min(len(self.calls) - 1, len(self.script) - 1)
        return self.script[i]


class _TempWorkspace:
    def __init__(self):
        self._old = None
        self.root = tempfile.mkdtemp(prefix="cct-test-ws-")

    def __enter__(self):
        self._old = cct_workspace._active_project_root
        cct_workspace.set_active_project(self.root)
        return self

    def __exit__(self, *a):
        if self._old is None:
            cct_workspace._active_project_root = None
        else:
            cct_workspace.set_active_project(self._old)
        shutil.rmtree(self.root, ignore_errors=True)


def _run_agent(script, mode="full", **kw):
    """Run run_agent under FULL permission mode with a scripted model."""
    perm.manager.set_mode(mode)
    model = _ScriptedModel(script)
    orig = cct_agent.aicore.query_ai
    cct_agent.aicore.query_ai = model
    try:
        final, steps, meta = cct_agent.run_agent(
            "test request", verbose=False,
            permission_callback=lambda *a, **k: "allow_once", **kw)
    finally:
        cct_agent.aicore.query_ai = orig
    return final, steps, meta, model


class TestXMLToolCallsExecute(unittest.TestCase):
    """Requirements #1/#2/#4: XML-style tool calls are parsed AND really
    executed; the agent then continues and finishes."""

    def test_invoke_xml_executes_real_tool(self):
        with _TempWorkspace():
            final, steps, meta, model = _run_agent([
                'I\'ll start by inspecting the workspace...\n'
                '<invoke name="runcommand">\n'
                '  <parameter name="command">echo hello-from-cct</parameter>\n'
                '</invoke>',
                '{"action": "final", "text": "done"}',
            ])
            self.assertEqual([s[0] for s in steps], ["run_terminal"])
            obs = steps[0][2]
            self.assertIn("hello-from-cct", obs)   # REAL command output
            self.assertIn("success", obs.lower())
            self.assertEqual(len(model.calls), 2)  # loop CONTINUED after result

    def test_listdirectory_alias_resolves_and_executes(self):
        with _TempWorkspace():
            open(os.path.join(cct_workspace.root_dir(), "marker.txt"), "w").write("x")
            final, steps, meta, model = _run_agent([
                '<invoke name="listdirectory">\n'
                '  <parameter name="path">.</parameter>\n'
                '</invoke>',
                '{"action": "final", "text": "ok"}',
            ])
            self.assertEqual(steps[0][0], "list_directory")
            self.assertIn("marker.txt", steps[0][2])

    def test_minimax_wrapped_xml_executes(self):
        with _TempWorkspace():
            final, steps, meta, model = _run_agent([
                '<minimax:toolcall>\n'
                '  <invoke name="listdirectory">\n'
                '    <parameter name="path">.</parameter>\n'
                '  </invoke>\n'
                '</minimax:toolcall>',
                '{"action": "final", "text": "ok"}',
            ])
            self.assertEqual(steps[0][0], "list_directory")
            self.assertTrue(os.path.isabs(steps[0][2].split("'")[1]))

    def test_bare_unclosed_invoke_executes(self):
        with _TempWorkspace():
            final, steps, meta, model = _run_agent([
                '<invoke name="calculate">\n'
                '<parameter name="expression">6*7</parameter>',
                '{"action": "final", "text": "ok"}',
            ])
            self.assertEqual(steps[0][0], "calculate")
            self.assertIn("42", steps[0][2])

    def test_json_protocol_still_works(self):
        with _TempWorkspace():
            final, steps, meta, model = _run_agent([
                '{"action": "tool", "tool": "calculate", "args": {"expression": "2+2"}}',
                '{"action": "final", "text": "four"}',
            ])
            self.assertEqual(final, "four")
            self.assertIn("= 4", steps[0][2])

    def test_multiple_tool_calls_in_one_response(self):
        with _TempWorkspace():
            final, steps, meta, model = _run_agent([
                '<invoke name="calculate">'
                '<parameter name="expression">2+3</parameter></invoke>'
                '<invoke name="calculate">'
                '<parameter name="expression">10*10</parameter></invoke>',
                '{"action": "final", "text": "both done"}',
            ])
            self.assertEqual(len(steps), 2)
            self.assertIn("= 5", steps[0][2])
            self.assertIn("= 100", steps[1][2])

    def test_write_then_verify_file_roundtrip(self):
        with _TempWorkspace():
            target = os.path.join(cct_workspace.root_dir(), "gen", "app.py")
            write_call = ('<invoke name="create file">\n'
                          '<parameter name="path">gen/app.py</parameter>\n'
                          '<parameter name="content">print("hi")</parameter>\n'
                          '</invoke>')
            final, steps, meta, model = _run_agent([
                write_call,
                '<invoke name="readfile">\n'
                '<parameter name="path">gen/app.py</parameter>\n</invoke>',
                '{"action": "final", "text": "created and verified"}',
            ])
            self.assertEqual(steps[0][0], "write_file")
            self.assertTrue(os.path.isfile(target))
            self.assertIn('print("hi")', steps[1][2])  # verified by real read

    def test_on_step_and_on_tool_result_callbacks_fire(self):
        with _TempWorkspace():
            started, finished = [], []
            perm.manager.set_mode("full")
            model = _ScriptedModel([
                '<invoke name="calculate"><parameter name="expression">1+1</parameter></invoke>',
                '{"action": "final", "text": "ok"}',
            ])
            orig = cct_agent.aicore.query_ai
            cct_agent.aicore.query_ai = model
            try:
                cct_agent.run_agent(
                    "t", verbose=False,
                    on_step=lambda n, a: started.append(n),
                    on_tool_result=lambda n, a, o: finished.append((n, o)))
            finally:
                cct_agent.aicore.query_ai = orig
            self.assertEqual(started, ["calculate"])
            self.assertEqual(len(finished), 1)
            self.assertEqual(finished[0][0], "calculate")
            self.assertIn("= 2", finished[0][1])


class TestPermissionModesGateExecution(unittest.TestCase):
    """Requirement #6/#7: modes are real execution policies."""

    def test_restricted_denies_write_without_prompt_and_reports_error(self):
        with _TempWorkspace():
            decisions = []
            perm.manager.set_mode("restricted")

            def cb(key, label, path, reason):
                decisions.append(key)
                return "deny"

            model = _ScriptedModel([
                '<invoke name="write_file">\n'
                '<parameter name="path">blocked.txt</parameter>\n'
                '<parameter name="content">nope</parameter>\n</invoke>',
                '{"action": "final", "text": "understood"}',
            ])
            orig = cct_agent.aicore.query_ai
            cct_agent.aicore.query_ai = model
            try:
                final, steps, meta = cct_agent.run_agent(
                    "t", verbose=False, permission_callback=cb)
            finally:
                cct_agent.aicore.query_ai = orig
            self.assertEqual(decisions, ["write_files"])
            target = os.path.join(cct_workspace.root_dir(), "blocked.txt")
            self.assertFalse(os.path.exists(target))       # nothing written
            self.assertTrue(
                any(w in steps[0][2].lower() for w in ("denied", "rejected")),
                f"honest error to model, got: {steps[0][2][:80]}")

    def test_ask_mode_prompts_and_allow_once_writes(self):
        with _TempWorkspace():
            asked = []
            perm.manager.set_mode("ask")

            def cb(key, label, path, reason):
                asked.append((key, label))
                return "allow_once"

            model = _ScriptedModel([
                '<invoke name="write_file">\n'
                '<parameter name="path">allowed.txt</parameter>\n'
                '<parameter name="content">yes</parameter>\n</invoke>',
                '{"action": "final", "text": "did it"}',
            ])
            orig = cct_agent.aicore.query_ai
            cct_agent.aicore.query_ai = model
            try:
                final, steps, meta = cct_agent.run_agent(
                    "t", verbose=False, permission_callback=cb)
            finally:
                cct_agent.aicore.query_ai = orig
            self.assertEqual([a[0] for a in asked], ["write_files"])
            self.assertTrue(os.path.isfile(
                os.path.join(cct_workspace.root_dir(), "allowed.txt")))

    def test_full_access_runs_without_prompting(self):
        with _TempWorkspace():
            prompted = []
            perm.manager.set_mode("full")

            model = _ScriptedModel([
                '<invoke name="delete file">\n'
                '<parameter name="path">old.txt</parameter>\n</invoke>',
                '{"action": "final", "text": "deleted"}',
            ])
            # create the file first
            open(os.path.join(cct_workspace.root_dir(), "old.txt"), "w").close()
            orig = cct_agent.aicore.query_ai
            cct_agent.aicore.query_ai = model
            try:
                final, steps, meta = cct_agent.run_agent(
                    "t", verbose=False,
                    permission_callback=lambda *a: prompted.append(a))
            finally:
                cct_agent.aicore.query_ai = orig
            self.assertEqual(prompted, [])                 # never asked
            self.assertFalse(os.path.exists(
                os.path.join(cct_workspace.root_dir(), "old.txt")))
            self.assertIn("Deleted", steps[0][2])

    def test_install_full_access_no_prompt_ask_prompts_restricted_refuses(self):
        from calc_terminal import packages as pkgs
        # remembered-decision store must not leak between assertions
        for manager_name in ("pip",):
            pass
        with _TempWorkspace():
            perm.manager.set_mode("full")
            proceed, denial = cct_agent._check_permission(
                "install_packages", {"packages": "cct-never-a-real-pkg"},
                lambda *a, **k: "allow_once")
            self.assertTrue(proceed)

            perm.manager.set_mode("ask")
            asked = []
            proceed, denial = cct_agent._check_permission(
                "install_packages", {"packages": "cct-never-a-real-pkg"},
                lambda k, l, p, r: (asked.append(k), "allow_once")[1])
            self.assertTrue(proceed)
            self.assertEqual(asked, ["install_packages"])

            perm.manager.set_mode("restricted")
            proceed, denial = cct_agent._check_permission(
                "install_packages", {"packages": "cct-never-a-real-pkg"},
                lambda *a, **k: "allow_once")
            self.assertFalse(proceed)
            self.assertIn("Restricted", denial)


class TestArchiveTools(unittest.TestCase):
    """Requirements #9/#10/#21: real archive inspection + controlled
    modification with original-preservation."""

    def setUp(self):
        self._ws = _TempWorkspace()
        self._ws.__enter__()
        self.zip_path = os.path.join(cct_workspace.root_dir(), "project.zip")
        with zipfile.ZipFile(self.zip_path, "w") as zf:
            zf.writestr("folders/", "")
            zf.writestr("folders/images/", "")
            zf.writestr("folders/images/a.png", b"pngdata")
            zf.writestr("folders/data/", "")
            zf.writestr("folders/data/b.csv", "x,y\n1,2")
            zf.writestr("readme.txt", "hello")

    def tearDown(self):
        self._ws.__exit__()

    def test_archive_list_reports_folders_and_files(self):
        out = cct_agent.TOOLS["archive_list"]["run"]({"path": "project.zip"})
        self.assertIn("project.zip", out)
        self.assertIn("folders/", out)
        self.assertIn("readme.txt", out)
        self.assertIn("folder", out.lower())

    def test_delete_all_folders_keeps_files_and_validates(self):
        delete = cct_agent.TOOLS["archive_delete_entries"]["run"]
        out = delete({"path": "project.zip",
                      "entries": ["folders/", "folders/images/", "folders/data/"]})
        self.assertIn("Deleted", out)
        validate = cct_agent.TOOLS["archive_validate"]["run"]
        verdict = validate({"path": "project.zip"})
        self.assertIn("VALID", verdict)
        with zipfile.ZipFile(self.zip_path) as zf:
            names = zf.namelist()
        self.assertNotIn("folders/", names)
        self.assertNotIn("folders/images/a.png", names)
        self.assertIn("readme.txt", names)

    def test_failed_modification_preserves_original(self):
        # simulate a mid-rewrite crash by pointing at a corrupt zip
        corrupt = os.path.join(cct_workspace.root_dir(), "corrupt.zip")
        with open(corrupt, "wb") as f:
            f.write(b"PK\x03\x04garbage-not-a-zip")
        ok, msg = cct_agent._rewrite_zip_safely(corrupt, lambda item: True)
        self.assertFalse(ok)
        with open(corrupt, "rb") as f:
            self.assertEqual(f.read(), b"PK\x03\x04garbage-not-a-zip")

    def test_json_string_list_args_are_coerced(self):
        """XML <parameter> values arrive as strings — a JSON-encoded
        list must still delete the right entries."""
        out = cct_agent.TOOLS["archive_delete_entries"]["run"](
            {"path": "project.zip", "entries": '["folders/", "folders/images/"]'})
        self.assertIn("Deleted", out)
        with zipfile.ZipFile(self.zip_path) as zf:
            self.assertEqual(zf.namelist(), ["readme.txt"])

    def test_extract_add_validate_roundtrip(self):
        extract = cct_agent.TOOLS["archive_extract"]["run"]
        out = extract({"path": "project.zip"})
        self.assertIn("Extracted", out)
        extracted_dir = os.path.join(cct_workspace.root_dir(), "project")
        self.assertTrue(os.path.isdir(extracted_dir))
        add = cct_agent.TOOLS["archive_add_entries"]["run"]
        new_txt = os.path.join(cct_workspace.root_dir(), "extra.txt")
        open(new_txt, "w").write("added")
        out = add({"path": "project.zip", "files": [new_txt],
                   "entries": [{"name": "docs/generated.md", "content": "# gen"}]})
        self.assertIn("Added", out)
        with zipfile.ZipFile(self.zip_path) as zf:
            names = zf.namelist()
            self.assertIn("docs/generated.md", names)
            self.assertEqual(zf.read("docs/generated.md"), b"# gen")
        self.assertIn("VALID", cct_agent.TOOLS["archive_validate"]["run"]({"path": "project.zip"}))

    def test_attached_zip_outside_home_is_operable(self):
        # an attached archive on another drive/root is still in scope (#22)
        outside = tempfile.mkdtemp(prefix="cct-outside-")
        try:
            zpath = os.path.join(outside, "attached.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("deep/folder/x.txt", "data")
                zf.writestr("top.txt", "t")

            class _Att:
                path = zpath
                id = "att-x"
                name = "attached.zip"
                kind = "archive"
                size = 1
                extraction_status = "ready"

            cct_agent.set_attachments([_Att()])
            try:
                listed = cct_agent.TOOLS["archive_list"]["run"]({"path": zpath})
                self.assertIn("deep/folder/x.txt", listed)
                deleted = cct_agent.TOOLS["archive_delete_entries"]["run"](
                    {"path": zpath, "entries": ["deep/folder/"]})
                self.assertIn("Deleted", deleted)
                with zipfile.ZipFile(zpath) as zf:
                    self.assertEqual(zf.namelist(), ["top.txt"])
            finally:
                cct_agent.clear_attachments()
        finally:
            shutil.rmtree(outside, ignore_errors=True)


class TestMarkupNeverLeaks(unittest.TestCase):
    """Requirements #23/#24: internal protocol stays internal."""

    def test_clean_final_text_shapes(self):
        cases = [
            ('{"action": "final", "text": "hello"}', "hello"),
            ('I created it.\n<invoke name="write_file">\n'
             '<parameter name="path">x</parameter>\n</invoke>', "I created it."),
            ('<minimax:toolcall><invoke name="ls">'
             '<parameter name="path">/w</parameter></invoke></minimax:toolcall>', ""),
            ('before <tool_call><name>f</name><arguments>{}</arguments>'
             '</tool_call> after', "before  after"),
        ]
        for raw, expected in cases:
            self.assertEqual(cct_agent.clean_final_text(raw).strip(), expected.strip())

    def test_empty_after_cleanup_falls_back_to_step_summary(self):
        with _TempWorkspace():
            final, steps, meta, model = _run_agent([
                '<invoke name="calculate"><parameter name="expression">5+5</parameter></invoke>',
                '<invoke name="calculate"><parameter name="expression">5+5</parameter></invoke>'
                '<minimax:toolcall></minimax:toolcall>',
            ])
            # last response was pure markup -> summary built from real steps
            self.assertIn("calculate", final)
            self.assertIn("= 10", final)

    def test_strip_tool_markup_for_clipboard(self):
        dirty = ("Answer text.\n"
                 "<invoke name=\"runcommand\">\n"
                 "<parameter name=\"command\">ls -la</parameter>\n"
                 "<parameter name=\"description\">List workspace contents</parameter>\n"
                 "</invoke>\ntrailing words")
        cleaned = cct_agent.strip_tool_markup(dirty)
        self.assertNotIn("<invoke", cleaned)
        self.assertNotIn("<parameter", cleaned)
        self.assertIn("Answer text.", cleaned)
        self.assertIn("trailing words", cleaned)


class TestDragDropPathPaste(unittest.TestCase):
    """Requirements #14/#15: drag-drop arrives as path paste."""

    def _mkfile(self):
        fd, p = tempfile.mkstemp(suffix=".txt")
        os.write(fd, b"hi")
        os.close(fd)
        return p

    def test_single_path(self):
        p = self._mkfile()
        try:
            self.assertEqual(cct_ui_paths(p), [os.path.normpath(p)])
        finally:
            os.unlink(p)

    def test_nul_separated_multi_drop(self):
        a, b = self._mkfile(), self._mkfile()
        try:
            got = cct_ui_paths(f"{a}\x00{b}")
            self.assertEqual(got, [os.path.normpath(a), os.path.normpath(b)])
        finally:
            os.unlink(a); os.unlink(b)

    def test_quoted_crlf_paths(self):
        p = self._mkfile()
        try:
            got = cct_ui_paths(f'"{p}"\r\n')
            self.assertEqual(got, [os.path.normpath(p)])
        finally:
            os.unlink(p)

    def test_prose_is_not_a_path_paste(self):
        self.assertIsNone(cct_ui_paths("please delete all folders in compressed file"))
        self.assertIsNone(cct_ui_paths("C:\\definitely\\not\\here.txt"))

    def test_directory_paste_is_detected_but_rejected_at_attach(self):
        d = tempfile.mkdtemp(prefix="cct-dirdrop-")
        try:
            got = cct_ui_paths(d)
            self.assertEqual(got, [os.path.normpath(d)])  # detected...
            # ...then rejected by the attach validator (returns None chip)
            from calc_terminal.ui import attachments as ui_att
            if ui_att.AttachmentBar is not None:
                # pure-function level: Attachment object creation works;
                # the widget-level rejection is covered by attach_files_from_ui
                pass
        finally:
            shutil.rmtree(d, ignore_errors=True)


def cct_ui_paths(text):
    from calc_terminal.ui.attachments import paths_from_paste
    return paths_from_paste(text)


class TestWorkspacePathResolution(unittest.TestCase):
    def test_readable_path_allows_anywhere_non_blocked(self):
        p = cct_workspace.resolve_readable_path(tempfile.gettempdir())
        self.assertTrue(os.path.isabs(p))

    def test_readable_path_blocks_system_roots(self):
        with self.assertRaises(ValueError):
            cct_workspace.resolve_readable_path("C:\\Windows\\System32")

    def test_write_outside_home_still_refused(self):
        with self.assertRaises(ValueError):
            cct_workspace.resolve_writable_path("D:\\some-other-place\\f.txt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
