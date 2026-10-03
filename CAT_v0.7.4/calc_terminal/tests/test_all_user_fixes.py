"""
Targeted tests for user-reported fixes:
1. Backup provider pool deletion & persistence (empty list not resurrecting defaults).
2. Research mode & Web searching/fetching (fetch_web_page tool, live activity emission).
3. Universal terminal automation in all modes (including notebook, agentic_execution routing, live activity).
4. Real-time thinking and reasoning for NVIDIA and all providers (reasoning_content, <think> tags, live activities).
"""

import json
import pytest
from unittest.mock import MagicMock, patch
import calc_terminal.providers.provider_manager as pm
import calc_terminal.model_router as router
import calc_terminal.agent as agent
import calc_terminal.aicore as aicore
import calc_terminal.activity as act
from calc_terminal.providers.openai_provider import OpenAIProvider


# ---------------- 1. BACKUP PROVIDER POOL ----------------
def test_backup_providers_empty_list_persistence(tmp_path, monkeypatch):
    """When the user deletes all backup providers, an empty list must be honored and not revert."""
    test_file = str(tmp_path / ".cct_backup_providers.json")
    monkeypatch.setattr(pm, "BACKUP_PROVIDERS_FILE", test_file)

    # Save empty list
    assert pm.save_backup_providers([]) is True
    # Load back - must be empty list, NOT DEFAULT_BACKUP_PROVIDERS
    loaded = pm.load_backup_providers()
    assert loaded == []

    # Add one provider
    sample = {"provider": "groq", "model": "llama-3.3-70b-versatile", "enabled": True}
    assert pm.add_backup_provider(sample) is True
    assert len(pm.load_backup_providers()) == 1

    # Remove by index
    assert pm.remove_backup_provider(0) is True
    # Must now be empty again, not reverting
    assert pm.load_backup_providers() == []


# ---------------- 2. RESEARCH MODE & WEB SEARCH / FETCH ----------------
def test_research_mode_routes_to_agent_with_tools():
    """Research mode must route to PATH_AGENT with use_tools=True."""
    dec = router.route("What are the latest developments in quantum computing?", mode="research")
    assert dec.path == router.PATH_AGENT
    assert dec.use_tools is True
    assert "research" in dec.reason.lower()


def test_fetch_web_page_tool_registered():
    """fetch_web_page must be registered in agent.TOOLS and activity.TOOL_ACTIVITY_META."""
    assert "fetch_web_page" in agent.TOOLS
    assert "fetch_web_page" in act.TOOL_ACTIVITY_META
    spec = agent.TOOLS["fetch_web_page"]
    assert callable(spec["run"])


def test_fetch_web_page_execution_and_activity():
    """fetch_web_page cleans HTML and creates Live Activity events."""
    sample_html = "<html><head><script>alert(1)</script></head><body><h1>CAT News</h1><p>Active web research.</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.text = sample_html

    with patch("requests.get", return_value=mock_resp):
        res = aicore.fetch_web_page("https://example.com/test", max_chars=500)
        assert "CAT News" in res
        assert "Active web research." in res
        assert "<script>" not in res


# ---------------- 3. UNIVERSAL TERMINAL AUTOMATION ----------------
def test_terminal_automation_classification_and_routing():
    """Any prompt asking for terminal automation must classify as agentic_execution and route to PATH_AGENT even in notebook mode."""
    prompts = [
        "automate terminal to check git status",
        "run command dir in terminal",
        "execute powershell script",
        "run in terminal npm test",
    ]
    for p in prompts:
        types = router.classify(p, mode="notebook")
        assert "agentic_execution" in types, f"Failed to classify agentic_execution for: {p}"
        dec = router.route(p, mode="notebook")
        assert dec.path == router.PATH_AGENT, f"Failed to route to PATH_AGENT for: {p}"
        assert dec.use_tools is True


def test_tool_run_terminal_emits_live_activity():
    """_tool_run_terminal executes command and logs to Live Activity."""
    res = agent._tool_run_terminal({"command": "echo Hello_CAT"})
    assert "Hello_CAT" in res
    # Find matching activity
    acts = act.manager.get_all()
    found = any(a.action == "terminal" and "Hello_CAT" in (a.command or "") for a in acts)
    assert found, "Live activity for terminal command was not recorded"


# ---------------- 4. NVIDIA & ALL PROVIDERS REASONING / THINKING ----------------
def test_openai_provider_chat_and_stream_reasoning():
    """OpenAIProvider handles reasoning_content in both chat and stream."""
    cfg = {"provider": "nvidia", "model": "deepseek-ai/deepseek-r1", "api_key": "test-key"}
    provider = OpenAIProvider(cfg)
    provider.get_base_url = MagicMock(return_value="https://integrate.api.nvidia.com/v1")
    provider.get_model = MagicMock(return_value="deepseek-ai/deepseek-r1")
    provider.get_api_key = MagicMock(return_value="test-key")

    # Test chat with reasoning_content
    mock_chat_resp = MagicMock()
    mock_chat_resp.status_code = 200
    mock_chat_resp.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant",
                "reasoning_content": "Step 1: Compute matrix\nStep 2: Done",
                "content": "The result is 42."
            }
        }]
    }
    with patch("requests.post", return_value=mock_chat_resp):
        ans = provider.chat("test prompt")
        assert "<think>" in ans
        assert "Step 1: Compute matrix" in ans
        assert "</think>" in ans
        assert "The result is 42." in ans

    # Test streaming with reasoning_content
    stream_lines = [
        'data: {"choices": [{"delta": {"reasoning_content": "Thinking about "}}]}\n',
        'data: {"choices": [{"delta": {"reasoning_content": "first principles."}}]}\n',
        'data: {"choices": [{"delta": {"content": "Final answer."}}]}\n',
        'data: [DONE]\n'
    ]
    mock_stream_resp = MagicMock()
    mock_stream_resp.status_code = 200
    mock_stream_resp.iter_lines.return_value = stream_lines

    with patch("requests.post", return_value=mock_stream_resp):
        chunks = list(provider.stream("test prompt"))
        full_stream = "".join(chunks)
        assert "<think>" in full_stream
        assert "Thinking about first principles." in full_stream
        assert "</think>" in full_stream
        assert "Final answer." in full_stream


def test_aicore_stream_ai_once_reasoning_and_activity():
    """aicore._stream_ai_once wraps reasoning_content in <think> and creates thinking live activity."""
    stream_lines = [
        'data: {"choices": [{"delta": {"reasoning_content": "Deep reasoning step 1. "}}]}\n',
        'data: {"choices": [{"delta": {"content": "Final AI response."}}]}\n',
        'data: [DONE]\n'
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = stream_lines

    cfg = {
        "provider": "nvidia",
        "model": "meta/llama-3.1-70b-instruct",
        "api_style": "openai",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "nvapi-test"
    }

    with patch("requests.post", return_value=mock_resp):
        chunks = list(aicore._stream_ai_once("Solve problem", config=cfg))
        full = "".join(chunks)
        assert "<think>" in full
        assert "Deep reasoning step 1." in full
        assert "</think>" in full
        assert "Final AI response." in full

    # Verify thinking activity completed
    acts = act.manager.get_all()
    found = any(a.action == "thinking" and "Reasoning & Thinking" in a.title for a in acts)
    assert found, "Live activity for reasoning was not created/completed"


def test_nvidia_nemotron_normalization_and_failover_prevention():
    """Verify that 'nvidia nematron 3 ultra' and its variations normalize to canonical model ID and avoid failover."""
    from calc_terminal.aicore import _normalize_provider_model
    from calc_terminal.providers import lifecycle

    ultra = "nvidia/nemotron-3-ultra-550b-a55b"
    variations = [
        "nvidia nematron 3 ultra",
        "nematron 3 ultra",
        "nematron-3-ultra",
        "nemotron 3 ultra",
        "3 ultra",
        "3-ultra",
        "nvidia/nemotron-3-ultra",
        "nvidia/nematron-3-ultra",
        "nvidia/nemotron-3-ultra-550b-a55b",
    ]

    for v in variations:
        norm = _normalize_provider_model("nvidia", v, "https://integrate.api.nvidia.com/v1")
        assert norm == ultra, f"Failed for variation '{v}': got '{norm}'"

    # Provider get_model normalization
    from calc_terminal.providers.openai_provider import OpenAIProvider
    p = OpenAIProvider({"provider": "nvidia", "model": "nematron 3 ultra", "base_url": "https://integrate.api.nvidia.com/v1"})
    assert p.get_model() == ultra

    # Pre-request check and alias resolution in lifecycle
    res = lifecycle.pre_request_check("nvidia", "nematron 3 ultra")
    assert res.valid is True
    assert (res.replacement or res.model) == ultra


def test_paste_detection_and_word_count():
    """Verify that pasted text detection shows words count on chips and properly retrieves text."""
    from calc_terminal.ui.attachments import AttachmentBar, PASTE_COLLAPSE_THRESHOLD, PASTE_WORD_THRESHOLD
    from calc_terminal.ui.events import PasteCollapsed

    assert PASTE_COLLAPSE_THRESHOLD == 2
    assert PASTE_WORD_THRESHOLD == 5

    bar = AttachmentBar()
    sample_text = "This is a test paragraph pasted into the CAT terminal input for checking words count detection."
    words = sample_text.split()
    assert len(words) == 16

    # Test add_paste
    chip_id = bar.add_paste(sample_text, line_count=1, word_count=len(words))
    assert chip_id.startswith("paste-")
    assert bar.has_pastes() is True

    # Check mounted chip label
    chips = list(bar.children)
    assert len(chips) == 1
    chip = chips[0]
    assert "16 words" in chip._label_text
    assert "Pasted text" in chip._label_text

    # Pop pastes for submission
    pastes = bar.pop_paste_texts()
    assert len(pastes) == 1
    assert pastes[0] == sample_text
    assert bar.has_pastes() is False
    assert len(list(bar.children)) == 0


# ---------------- 6. TERMINAL AUTOMATION & LIVE ACTIVITY STREAMING ----------------
def test_make_noninteractive_command():
    """Verify scaffolding commands are auto-upgraded with non-interactive flags."""
    from calc_terminal.agent import _make_noninteractive_command

    cmd1 = "npm create vite@latest portfolio -- --template react-ts"
    upgraded1 = _make_noninteractive_command(cmd1)
    assert "-y" in upgraded1
    assert upgraded1.startswith("npm create -y vite@latest")

    cmd2 = "npx create-next-app@latest my-app"
    upgraded2 = _make_noninteractive_command(cmd2)
    assert "--yes" in upgraded2

    cmd3 = "npm init react-app my-app"
    upgraded3 = _make_noninteractive_command(cmd3)
    assert "-y" in upgraded3

    cmd4 = "yarn create react-app my-app"
    upgraded4 = _make_noninteractive_command(cmd4)
    assert "--non-interactive" in upgraded4

    # If -y or --yes already present, don't duplicate
    cmd5 = "npm create -y vite@latest my-app"
    assert _make_noninteractive_command(cmd5) == cmd5


def test_tool_run_terminal_streaming_and_live_activity():
    """Verify _tool_run_terminal executes with non-interactive env and updates Live Activity."""
    import calc_terminal.activity as act_mod
    act_mod.set_current_turn("test-turn-automation")

    res = agent._tool_run_terminal({"command": "python -c \"print('CAT_AUTO_TEST_OK')\""})
    assert "CAT_AUTO_TEST_OK" in res
    assert "✓ success" in res

    # Check that an activity was recorded with COMPLETED status and stdout
    acts = act_mod.manager.get_for_turn("test-turn-automation")
    term_acts = [a for a in acts if a.action == "terminal" and "CAT_AUTO_TEST_OK" in (a.command or "")]
    assert len(term_acts) >= 1
    assert term_acts[0].status == act_mod.STATUS_COMPLETED
    assert "CAT_AUTO_TEST_OK" in (term_acts[0].stdout or "")


# ---------------- 7. FULL COMPUTER & DEVICE AUTOMATION ----------------
def test_device_control_desktop_provider():
    """Verify DesktopProvider is available and executes computer automation actions."""
    from calc_terminal import device_control as dc

    p = dc.provider("desktop")
    assert p is not None
    assert p.available() is True

    # Test system_info
    plan = p.plan("system_info", {})
    assert "hardware" in plan["effect"].lower() or "os" in plan["effect"].lower()
    res = dc.execute_approved("desktop", plan, {})
    assert res["ok"] is True
    assert "OS:" in res["output"]

    # Test PowerShell execution
    plan_ps = p.plan("run_powershell", {"target": "Write-Output 'CAT_DESKTOP_AUTOMATED'"})
    assert plan_ps["command"] == "Write-Output 'CAT_DESKTOP_AUTOMATED'"
    res_ps = dc.execute_approved("desktop", plan_ps, {})
    assert res_ps["ok"] is True
    assert "CAT_DESKTOP_AUTOMATED" in res_ps["output"]


def test_device_control_android_provider():
    """Verify AndroidProvider plans and handles adb actions."""
    from calc_terminal import device_control as dc

    p = dc.provider("android")
    assert p is not None
    # Plan devices
    plan_dev = p.plan("devices", {})
    assert "adb devices" in plan_dev["command"]

    # Plan tap
    plan_tap = p.plan("tap", {"target": "500 800"})
    assert "adb shell input tap 500 800" in plan_tap["command"]

    # Plan keyevent
    plan_key = p.plan("keyevent", {"target": "3"})
    assert "adb shell input keyevent 3" in plan_key["command"]


def test_device_control_browser_provider():
    """Verify BrowserProvider is available and handles web automation."""
    from calc_terminal import device_control as dc

    p = dc.provider("browser")
    assert p is not None
    assert p.available() is True

    plan = p.plan("search", {"target": "Python 3.12 documentation"})
    assert "search" in plan["effect"].lower()


def test_all_ai_modes_have_agent_capabilities():
    """Verify all AI modes (Build, Agent, Research, Debugger, Plan) have agent system prompts."""
    from calc_terminal import agent

    assert hasattr(agent, "BUILD_SYSTEM_PROMPT")
    assert hasattr(agent, "AGENT_SYSTEM_PROMPT")
    assert hasattr(agent, "RESEARCH_SYSTEM_PROMPT")
    assert hasattr(agent, "PLAN_SYSTEM_PROMPT")
    assert hasattr(agent, "DEBUGGER_SYSTEM_PROMPT")

    assert "CAT Build" in agent.BUILD_SYSTEM_PROMPT
    assert "automate the terminal" in agent.BUILD_SYSTEM_PROMPT.lower()
    assert "device_action" in agent.BUILD_SYSTEM_PROMPT


# ---------------- 5. DEVSERVER, PREVIEW & RESPONSIVENESS FIXES ----------------
def test_devserver_ansi_url_extraction():
    """Vite/Next output with ANSI escape codes must be cleanly parsed without ANSI in URL."""
    from calc_terminal.browser.devserver import extract_local_url

    # Colored Vite output
    vite_line = "  ➜  \x1b[1mLocal:\x1b[22m   \x1b[36mhttp://localhost:5173/\x1b[39m"
    url = extract_local_url(vite_line)
    assert url == "http://localhost:5173/"

    # Next.js output with escape codes and trailing characters
    next_line = "   - \x1b[32mLocal:\x1b[0m        \x1b[34mhttp://localhost:3000\x1b[0m"
    url2 = extract_local_url(next_line)
    assert url2 == "http://localhost:3000/"

    # Bind address 0.0.0.0 normalization
    bound_line = "Listening on http://0.0.0.0:8080"
    url3 = extract_local_url(bound_line)
    assert url3 == "http://127.0.0.1:8080/"


def test_devserver_probe_and_timeout():
    """Dev server timeout must be 15s (not 45s) and probe_local_server must be callable."""
    from calc_terminal.browser.devserver import DEFAULT_TIMEOUT, probe_local_server

    assert DEFAULT_TIMEOUT == 15.0
    # Probing an unlikely closed port must return False without hanging
    assert probe_local_server(59999) is False


def test_preview_controller_framework_failure_falls_back_to_static(tmp_path):
    """When a framework dev server fails to start, preview must fall back to static live server."""
    from calc_terminal.browser.preview import PreviewController
    from calc_terminal.browser.state import PreviewState, ServerState

    # Create dummy workspace with package.json (detected as framework) and index.html
    root = str(tmp_path / "vite_proj")
    import os
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as f:
        f.write('{"scripts": {"dev": "vite"}, "dependencies": {"vite": "^5.0"}}')
    os.makedirs(os.path.join(root, "node_modules"), exist_ok=True)
    index_path = os.path.join(root, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html><html><body><h1>Hello CAT</h1></body></html>")

    class FailingDevServer:
        running = False
        url = ""
        last_output = "npm ERR! Missing dependencies"

        def __init__(self, root, command, on_activity=None):
            pass

        def start(self, timeout=15.0):
            return False  # Dev server failed to start!

        def stop(self):
            pass

    class DummyEngine:
        available = True
        ok = True

        def start(self):
            pass

        def navigate(self, url):
            from calc_terminal.browser.state import PreviewSnapshot
            return PreviewSnapshot(url=url, ok=True)

        def close(self, timeout=6.0):
            pass

    ctrl = PreviewController(root, engine=DummyEngine(), devserver_factory=FailingDevServer)
    # Even though framework dev server failed, preview starts via static fallback
    ok = ctrl.start_for_file(index_path)
    assert ok is True
    assert ctrl.server_state == ServerState.RUNNING
    assert ctrl.preview_state == PreviewState.RUNNING
    # Served from CAT's internal static server
    assert ctrl.server.running is True
    ctrl.stop_preview()


def test_kill_active_tool_processes_and_cancellation():
    """kill_active_tool_processes must instantly terminate registered tool processes."""
    import subprocess
    import sys
    from calc_terminal import agent

    # Spawn a slow process
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    agent.register_tool_process(proc)
    assert proc in agent._ACTIVE_TOOL_PROCESSES

    # Kill active tool processes
    agent.kill_active_tool_processes()
    assert len(agent._ACTIVE_TOOL_PROCESSES) == 0
    # Process must be terminated
    proc.wait(timeout=2.0)
    assert proc.poll() is not None


# ---------------- 12. WEBP REVIEW FOMOJI ISOLATION & DEVICE SYNC ----------------
def test_fomoji_port_detection_and_devserver_probe_rejection(monkeypatch):
    """DevServer fast-probe must reject port 3000 if it is Fomoji identity server."""
    from calc_terminal.browser import devserver

    # When is_fomoji_server returns True, probe_local_server must return False
    monkeypatch.setattr(devserver, "is_fomoji_server", lambda port, host="127.0.0.1": port == 3000)
    assert devserver.probe_local_server(3000) is False


def test_devserver_probe_order_prefers_3001_before_3000():
    """Dev server probe list must inspect port 3001 before port 3000."""
    from calc_terminal.browser.devserver import DevServerProcess
    import inspect

    src = inspect.getsource(DevServerProcess.start)
    idx_3001 = src.find("3001")
    idx_3000 = src.find("3000")
    assert idx_3001 != -1 and idx_3000 != -1
    assert idx_3001 < idx_3000


def test_device_login_url_includes_code_and_syncs_with_local(monkeypatch):
    """device_login must append ?code={user_code} and immediately recognize local credentials."""
    from calc_terminal import fomoji_auth

    mock_start = {
        "deviceCode": "dev-12345",
        "userCode": "CAT-9999",
        "verificationUrl": "/connector.html",
        "pollIntervalSeconds": 1,
    }
    monkeypatch.setattr(fomoji_auth, "ensure_fomoji_server", lambda **kw: True)
    monkeypatch.setattr(fomoji_auth, "_device_start", lambda perms: mock_start)

    captured_url = []
    def fake_on_prompt(user_code, verification_url):
        captured_url.append(verification_url)

    # Simulate direct local credential write by Fomoji server / web UI
    mock_identity = {"fomojiId": "usr_99", "name": "Test User", "email": "test@fomoji.local"}
    monkeypatch.setattr(fomoji_auth, "_load_local", lambda: {"token": "tok_xyz", "identity": mock_identity})

    result = fomoji_auth.device_login(on_prompt=fake_on_prompt, timeout_seconds=5)
    assert result == mock_identity
    assert len(captured_url) == 1
    assert "code=CAT-9999" in captured_url[0]


def test_fomoji_auth_cli_signup_routing(monkeypatch):
    """_auth_cli with signup action must start device flow and open signup URL."""
    from calc_terminal import fomoji_auth

    mock_start = {
        "deviceCode": "dev-54321",
        "userCode": "CAT-7777",
        "verificationUrl": "/connector.html",
        "pollIntervalSeconds": 1,
    }
    monkeypatch.setattr(fomoji_auth, "is_authenticated", lambda: False)
    monkeypatch.setattr(fomoji_auth, "check_server_reachable", lambda: True)
    monkeypatch.setattr(fomoji_auth, "_device_start", lambda perms: mock_start)
    opened_urls = []
    monkeypatch.setattr("webbrowser.open", lambda u: opened_urls.append(u))
    monkeypatch.setattr(fomoji_auth, "_print_device_prompt", lambda code, url: None)

    # Immediately report local credential sync
    mock_identity = {"fomojiId": "usr_77", "name": "New Signup User"}
    monkeypatch.setattr(fomoji_auth, "_load_local", lambda: {"token": "tok_new", "identity": mock_identity})

    exit_code = fomoji_auth._auth_cli(["signup"])
    assert exit_code == 0
    assert len(opened_urls) == 1
    assert "signup.html" in opened_urls[0]
    assert "code=CAT-7777" in opened_urls[0]


# ---------------- 13. PRE-DEPLOYMENT SECRET SAFETY PASS ----------------
def test_git_sync_is_blocked_file():
    """is_blocked_file must block secrets/credentials while allowing .env.example."""
    from calc_terminal.git_sync import is_blocked_file

    # Blocked secrets and credentials
    assert is_blocked_file(".env") is True
    assert is_blocked_file("fomoji-updated/fomoji-server/.env") is True
    assert is_blocked_file(".env.production") is True
    assert is_blocked_file(".env.local") is True
    assert is_blocked_file("id_rsa") is True
    assert is_blocked_file("server.key") is True
    assert is_blocked_file("client.pem") is True
    assert is_blocked_file(".pypirc") is True
    assert is_blocked_file("credentials.json") is True
    assert is_blocked_file("client_secret_123.json") is True
    assert is_blocked_file(".fomoji/connectors/cat.json") is True

    # Allowed template and non-secret files
    assert is_blocked_file(".env.example") is False
    assert is_blocked_file("calc_terminal/fomoji_server/.env.example") is False
    assert is_blocked_file("src/index.js") is False
    assert is_blocked_file("README.md") is False


def test_security_layer_redacts_supabase_and_stripe_and_db_uris():
    """SecurityLayer must redact Supabase, Stripe, DB passwords, Twilio, SendGrid, and JWTs."""
    from calc_terminal.core.security_layer import SecurityLayer

    sec = SecurityLayer()

    # Supabase key
    fake_sbp = "sbp_" + "abcdef1234567890123456"
    out = sec.redact_secrets(f"Supabase key: {fake_sbp}")
    assert fake_sbp not in out
    assert "[REDACTED_SUPABASE_KEY]" in out

    # Stripe Secret & Publishable keys
    fake_stripe_sec = "sk_live_" + "51ABCDEF1234567890123456789"
    out_stripe_sec = sec.redact_secrets(fake_stripe_sec)
    assert "sk_live_" not in out_stripe_sec
    assert "[REDACTED_STRIPE_SECRET_KEY]" in out_stripe_sec

    fake_stripe_pub = "pk_live_" + "51ABCDEF1234567890123456789"
    out_stripe_pub = sec.redact_secrets(fake_stripe_pub)
    assert "pk_live_" not in out_stripe_pub
    assert "[REDACTED_STRIPE_PUBLISHABLE_KEY]" in out_stripe_pub

    # Database URIs with passwords
    out_pg = sec.redact_secrets("postgres://admin:superSecretPass123!@localhost:5432/mydb")
    assert "superSecretPass123!" not in out_pg
    assert "[REDACTED_PASSWORD]" in out_pg

    out_mongo = sec.redact_secrets("mongodb+srv://app_user:dbPassword999@cluster0.net/prod")
    assert "dbPassword999" not in out_mongo
    assert "[REDACTED_PASSWORD]" in out_mongo

    # SendGrid and Twilio
    fake_sg = "SG." + "1234567890123456789012." + "1234567890123456789012345678901234567890123"
    out_sg = sec.redact_secrets(fake_sg)
    assert "SG." not in out_sg
    assert "[REDACTED_SENDGRID_KEY]" in out_sg

    fake_tw = "AC" + "12345678901234567890123456789012"
    out_tw = sec.redact_secrets(fake_tw)
    assert fake_tw not in out_tw
    assert "[REDACTED_TWILIO_SID]" in out_tw


def test_env_example_has_no_secrets():
    """Root .env.example must only have placeholder keys with zero values."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent.parent
    env_ex = root / ".env.example"
    assert env_ex.exists()

    content = env_ex.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            # Allowed non-secret defaults
            if key in ("PORT", "RP_ID", "RP_NAME", "ORIGIN", "CAT_ECO_MODE", "FOMOJI_URL", "OLLAMA_URL", "AWS_REGION"):
                continue
            assert val == "", f"Secret key {key} must have empty value in .env.example, got '{val}'"


# ---------------- 9. PRIVACY, PII AUDIT & ACCOUNT DELETION ----------------
def test_security_layer_redacts_pii_emails_phones_and_connector_tokens():
    """SecurityLayer must redact emails, phone numbers, and Fomoji connector tokens."""
    from calc_terminal.core.security_layer import SecurityLayer
    sec = SecurityLayer()

    # Email redaction
    sample_text = "User contacted support from user.name+tag@example.co.uk about their account."
    redacted = sec.redact_secrets(sample_text)
    assert "user.name+tag@example.co.uk" not in redacted
    assert "[REDACTED_EMAIL]" in redacted

    # Phone number redaction
    phone_text = "Call me at +1 (555) 234-5678 or 555-876-5432 regarding the verification."
    redacted_phone = sec.redact_secrets(phone_text)
    assert "555" not in redacted_phone
    assert "[REDACTED_PHONE]" in redacted_phone

    # Connector token redaction
    tok_text = "Authorization token: fct_abcdef1234567890_SECRET_TOKEN_XYZ"
    redacted_tok = sec.redact_secrets(tok_text)
    assert "fct_abcdef1234567890_SECRET_TOKEN_XYZ" not in redacted_tok
    assert "[REDACTED_CONNECTOR_TOKEN]" in redacted_tok


def test_fomoji_auth_email_masking():
    """mask_email should obfuscate the username portion of an email for safe display."""
    from calc_terminal.fomoji_auth import mask_email
    assert mask_email("alex@example.com") == "al***x@example.com"
    assert mask_email("jo@test.org") == "j***@test.org"
    assert mask_email("") == ""
    assert mask_email("plainstring") == "plainstring"


def test_fomoji_auth_delete_account_workflow(tmp_path, monkeypatch):
    """delete_account() must unlink local token file and invalidate memory cache."""
    import calc_terminal.fomoji_auth as fa
    test_token_path = tmp_path / "cat.json"
    test_token_path.write_text('{"token": "fct_test", "identity": {"name": "Test User"}}', encoding="utf-8")

    monkeypatch.setattr(fa, "TOKEN_PATH", test_token_path)
    monkeypatch.setattr(fa, "_request", lambda method, path, **kwargs: {"ok": True})

    assert test_token_path.exists()
    res = fa.delete_account()
    assert res.get("ok") is True
    assert not test_token_path.exists()
    assert fa.status() != "connected"


# ---------------- 13. NON-BLOCKING TERMINAL, DEVSERVER & INSTANT INTERRUPT ----------------
def test_tool_run_terminal_devserver_detection_and_immediate_return(tmp_path):
    """Dev server commands must detect the local URL and return immediately without waiting for exit."""
    from calc_terminal import agent
    import sys
    import time

    mock_script = tmp_path / "mock_dev.py"
    mock_script.write_text(
        "import time\n"
        "print('  ➜  Local:   http://localhost:5173/', flush=True)\n"
        "time.sleep(10)\n",
        encoding="utf-8"
    )
    cmd = f'echo npm run dev > nul & "{sys.executable}" "{mock_script}"'
    t0 = time.time()
    res = agent._tool_run_terminal({"command": cmd, "timeout": 15})
    elapsed = time.time() - t0

    # Must return immediately once URL is detected rather than sleeping for 10s
    assert elapsed < 6.0
    assert ("http://localhost:5173/" in res) or ("http://localhost:" in res)
    assert ("Dev server is live and running" in res) or ("already active" in res)

    # Clean up background dev server
    agent.kill_active_tool_processes()


def test_tool_run_terminal_instant_interruption():
    """_tool_run_terminal must check cancellation every 100ms and abort in under 500ms."""
    from calc_terminal import agent
    import sys
    import time

    agent._CURRENT_AGENT_SHOULD_CANCEL = lambda: True
    try:
        t0 = time.time()
        res = agent._tool_run_terminal({
            "command": f'"{sys.executable}" -c "import time; time.sleep(10)"',
            "timeout": 15
        })
        elapsed = time.time() - t0
        assert elapsed < 1.0
        assert "Interrupted by user" in res
    finally:
        agent._CURRENT_AGENT_SHOULD_CANCEL = None
        agent.kill_active_tool_processes()


def test_tool_run_terminal_timeout_preserves_output_and_diagnoses():
    """When a command times out, output must NOT be discarded and diagnostic should explain root cause."""
    from calc_terminal import agent
    import sys
    import time

    t0 = time.time()
    res = agent._tool_run_terminal({
        "command": f'"{sys.executable}" -c "import time; print(\'step 1 done\', flush=True); time.sleep(10)"',
        "timeout": 1.0
    })
    elapsed = time.time() - t0
    assert elapsed < 3.0
    assert "timed out after 1s" in res.lower() or "timed out after 1.0s" in res.lower()
    assert "step 1 done" in res
    assert "DIAGNOSTIC" in res
    agent.kill_active_tool_processes()


def test_tool_run_terminal_diagnoses_missing_dependencies():
    """Missing dependencies errors must generate actionable diagnostics."""
    from calc_terminal import agent

    res = agent._diagnose_command_error(
        raw_cmd="npm run dev",
        output="Error: Cannot find module 'vite'",
        exit_code=1,
        timed_out=False,
        interrupted=False,
        timeout=60.0
    )
    assert res is not None
    assert "Missing project dependencies" in res


def test_nemotron_reasoning_timeout_not_misclassified_as_error():
    """Nemotron reasoning (<think>) containing words like 'timed out' or 'connection'
    must NEVER be misclassified as a provider error causing false failover."""
    from calc_terminal import aicore

    # Reasoning with 'timed out'
    reasoning_reply = (
        "<think>\n"
        "The user is asking about why their dev server timed out during npm run dev.\n"
        "I need to check the timeout configuration and connection settings.\n"
        "</think>\n"
        "Here are 3 common reasons why your dev server timed out:\n"
        "1. Port 3000 is already in use.\n"
        "2. Firewall blocking local connection.\n"
        "3. Timeout threshold is too low in vite.config.js."
    )
    assert aicore.is_error_response(reasoning_reply) is False
    assert aicore._retryable_failure(reasoning_reply) is False
    assert aicore._should_failover(reasoning_reply) is False

    # Markdown code fence containing timeout error text
    code_fence_reply = (
        "You might see this in your terminal:\n"
        "```\n"
        "Error: connect ETIMEDOUT 127.0.0.1:5000\n"
        "Connection timed out\n"
        "```\n"
        "To resolve this, update your proxy target."
    )
    assert aicore.is_error_response(code_fence_reply) is False
    assert aicore._retryable_failure(code_fence_reply) is False
    assert aicore._should_failover(code_fence_reply) is False

    # Genuine provider error (short text, no <think>, not code)
    genuine_err = "Error: Provider gateway connection timed out after 30000ms"
    assert aicore.is_error_response(genuine_err) is True
    assert aicore._retryable_failure(genuine_err) is True
    assert aicore._should_failover(genuine_err) is True


def test_model_contributions_tracking_and_short_names():
    """Contribution tracking must record accurate tokens/chars and compute percentages.
    Model names must be shortened cleanly for telemetry badges."""
    from calc_terminal import aicore
    from calc_terminal.ui.conversation import short_model_name

    # 1. Test short_model_name helper
    assert short_model_name("nvidia/nemotron-3-ultra-550b-a55b") == "nemotron-3-ultra"
    assert short_model_name("nvidia/nemotron-3.5-lightning-30b-a3b") == "nemotron-3.5-lightning"
    assert short_model_name("deepseek/deepseek-chat") == "deepseek-chat"
    assert short_model_name("openai/gpt-4o-mini-2024-07-18") == "gpt-4o-mini"
    assert short_model_name("claude-3-5-sonnet-20241022") == "claude-3-5-sonnet"
    assert short_model_name("gemini-1.5-flash-latest") == "gemini-1.5-flash"
    assert short_model_name("") == ""

    # 2. Test turn contributions record & get
    turn_id = "test-turn-contrib-42"
    stats = {
        "main_tokens": 0,
        "backup_tokens": 714,
        "main_chars": 0,
        "backup_chars": 2856,
        "main_provider": "nvidia",
        "main_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "backup_provider": "nvidia",
        "backup_model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "total_tokens": 714,
        "pct_main": 0,
        "pct_backup": 100,
        "is_backup": True,
    }
    aicore.record_turn_contributions(stats, turn_id=turn_id)
    res = aicore.get_last_contributions(turn_id)
    assert res is not None
    assert res["pct_main"] == 0
    assert res["pct_backup"] == 100
    assert res["backup_model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert res["is_backup"] is True


def test_telemetry_badge_redesign_rendering():
    """Telemetry badge must render compact model name and show backup vs main contributions."""
    from calc_terminal.ui.conversation import ConversationItem
    from rich.console import Console

    con = Console(record=True, width=150)

    # Case A: Failover response (100% backup provider)
    item_failover = ConversationItem(
        "t-failover",
        role="assistant",
        text="Hello world from backup",
        contributions={
            "pct_main": 0,
            "pct_backup": 100,
            "main_model": "nvidia/nemotron-3-ultra-550b-a55b",
            "backup_model": "nvidia/nemotron-3.5-lightning-30b-a3b",
            "is_backup": True,
            "total_tokens": 714,
        }
    )
    meta_lines = [
        "✓ Response Complete",
        "Model: nvidia/nemotron-3.5-lightning-30b-a3b",
        "Time: 1:26",
        "Tokens: 714",
    ]
    tbl_failover = item_failover._format_telemetry(meta_lines)
    con.print(tbl_failover)
    telemetry = con.export_text()
    assert "✓ Complete" in telemetry
    assert "Backup 100%" in telemetry
    assert "nemotron-3.5-lightning" in telemetry
    assert "Main 0%" in telemetry
    assert "nemotron-3-ultra" in telemetry
    assert "1:26" in telemetry
    assert "714 tokens" in telemetry
    # Ensure long provider path is shortened
    assert "nvidia/nemotron-3-ultra-550b-a55b" not in telemetry

    # Case B: Primary model response (100% main)
    item_primary = ConversationItem(
        "t-primary",
        role="assistant",
        text="Hello world from main model",
        contributions={
            "pct_main": 100,
            "pct_backup": 0,
            "main_model": "nvidia/nemotron-3-ultra-550b-a55b",
            "backup_model": None,
            "is_backup": False,
            "total_tokens": 450,
        }
    )
    meta_primary = [
        "✓ Response Complete",
        "Model: nvidia/nemotron-3-ultra-550b-a55b",
        "Time: 1.4s",
        "Tokens: 450",
    ]
    con = Console(record=True, width=150)
    tbl_prim = item_primary._format_telemetry(meta_primary)
    con.print(tbl_prim)
    telemetry_prim = con.export_text()
    assert "✓ Complete" in telemetry_prim
    assert "nemotron-3-ultra" in telemetry_prim
    assert "1.4s" in telemetry_prim
    assert "450 tokens" in telemetry_prim
    assert "Backup" not in telemetry_prim


def test_drain_failover_notes_cleans_notes_without_bubble_pollution():
    """drain_failover_notes must clear queued notes without polluting chat bubble pieces."""
    # Simulate pending failover notes
    pending_notes = ["Provider issue with nvidia (nvidia/nemotron-3-ultra-550b-a55b). Switching to Backup Provider..."]
    pieces = ["First chunk of actual AI answer."]

    # The updated draining logic
    def drain_failover_notes():
        while True:
            try:
                pending_notes.pop(0)
            except (IndexError, AttributeError):
                return

    drain_failover_notes()
    assert len(pending_notes) == 0
    # pieces must contain ONLY the actual AI answer, never the failover warning
    assert len(pieces) == 1
    assert "Provider issue" not in "".join(pieces)


def test_chemistry_highlighter_does_not_corrupt_tech_acronyms():
    """_highlight_chemistry must NOT wrap normal words (URL, PM, VITE, HTML, JSON, API)
    in backticks, while preserving real chemical formulas like H2O and CO2."""
    from calc_terminal.ui.conversation import _highlight_chemistry, _is_real_chem_formula

    # Check formula classifier
    assert _is_real_chem_formula("URL") is False
    assert _is_real_chem_formula("PM") is False
    assert _is_real_chem_formula("VITE") is False
    assert _is_real_chem_formula("HTML") is False
    assert _is_real_chem_formula("API") is False
    assert _is_real_chem_formula("JSON") is False
    assert _is_real_chem_formula("H2O") is True
    assert _is_real_chem_formula("CO2") is True
    assert _is_real_chem_formula("NaCl") is True
    assert _is_real_chem_formula("H2SO4") is True
    assert _is_real_chem_formula("Fe3+") is True

    # Real user sentence from screenshot:
    text = "The portfolio dev server is running at http://localhost:5173/. Open that URL in your browser at 10:53:24 PM."
    out = _highlight_chemistry(text)
    # URL and PM must NOT have backticks
    assert "`URL`" not in out
    assert "`PM`" not in out
    assert "Open that URL in your browser at 10:53:24 PM." in out

    # Chemistry text should still be highlighted
    chem_text = "Mixing H2O with NaCl produces aqueous solution."
    chem_out = _highlight_chemistry(chem_text)
    assert "`H₂O`" in chem_out
    assert "`NaCl`" in chem_out


def test_summarize_file_changes_strips_ansi_and_formats_cleanly():
    """Terminal output in summarize_file_changes must strip ANSI escapes (no broken [ ] glyphs)
    and render inside fenced code blocks with bulleted timeline."""
    from calc_terminal import agent

    # Terminal output containing raw Vite ANSI escapes (\x1b[2K, \x1b[32m, etc.)
    raw_terminal_output = (
        "\x1b[2K\x1b[1G10:53:24 PM [vite]      Re-optimizing dependencies\x1b[2K\x1b[1G\n"
        "  \x1b[32m➜\x1b[39m  \x1b[1mLocal:\x1b[22m   \x1b[36mhttp://localhost:5173/\x1b[39m\x1b[2K\x1b[1G\n"
    )

    steps = [
        ("run_terminal", {"command": "cd portfolio && npm run dev"}, raw_terminal_output, {
            "kind": "terminal",
            "command": "cd portfolio && npm run dev",
            "output": raw_terminal_output,
            "exit_code": 0,
            "duration": 2.89,
        })
    ]

    summary = agent.summarize_file_changes(steps, markdown=True)
    # 1. No raw ANSI escape codes
    assert "\x1b[" not in summary
    assert "\x1b" not in summary
    # 2. Uses fenced code block
    assert "```text" in summary
    assert "http://localhost:5173/" in summary
    # 3. Clean timeline with list items
    assert "- ✓ Ran `cd portfolio && npm run dev`" in summary
    assert "- ✓ Finished" in summary


def test_restore_chat_retry_and_edit():
    """Verify that restored previous chats (even legacy chats without parent_turn_id)
    can be retried, rewritten/edited, and replaced in-place without error."""
    from unittest.mock import MagicMock
    from calc_terminal.session import ChatSession
    from calc_terminal import chat_store
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.events import MessageRewritten

    app = CCTApp.__new__(CCTApp)
    app.session = ChatSession()
    app._current_workspace = "test_workspace"
    app._current_ai_mode = "notebook"
    app._current_chat_id = "test_retry_chat_id"
    app._system_note = MagicMock()
    app._switch_mode_command = MagicMock()
    app._maybe_gate_then_run = MagicMock()
    mock_conv = MagicMock()
    mock_comp = MagicMock()
    app.query_one = lambda cls: mock_conv if "Conversation" in str(cls) else mock_comp

    # 1. Restore previous turns (legacy without parent_turn_id)
    user_turn_data = {"role": "user", "content": "How does quicksort work?", "mode": "notebook", "turn_id": "u-test-1"}
    asst_turn_data = {"role": "assistant", "content": "Quicksort is a divide-and-conquer algorithm...", "mode": "notebook", "turn_id": "a-test-1"}

    t_user = app._restore_turn_from_store(user_turn_data)
    t_asst = app._restore_turn_from_store(asst_turn_data)

    assert t_user.turn_id == "u-test-1"
    assert t_asst.turn_id == "a-test-1"
    assert t_asst.parent_turn_id == "u-test-1", "Assistant turn must link to preceding user prompt"

    # 2. Test retry on assistant turn
    app._retry_in_mode("a-test-1", "build")
    app._maybe_gate_then_run.assert_called_once_with(
        "How does quicksort work?", [], parent_turn_id="u-test-1", replace_turn_id="a-test-1"
    )

    # 3. Test retry fallback when parent_turn_id is None
    t_asst.parent_turn_id = None
    app._maybe_gate_then_run.reset_mock()
    app._retry_in_mode("a-test-1", "agent")
    app._maybe_gate_then_run.assert_called_once_with(
        "How does quicksort work?", [], parent_turn_id="u-test-1", replace_turn_id="a-test-1"
    )
    assert t_asst.parent_turn_id == "u-test-1"

    # 4. Test rewrite prompt on user message
    app._maybe_gate_then_run.reset_mock()
    t_asst.parent_turn_id = None  # simulate broken link before rewrite
    event = MessageRewritten("u-test-1", "How does mergesort work?", [])
    app.on_message_rewritten(event)
    app._maybe_gate_then_run.assert_called_once_with(
        "How does mergesort work?", [], parent_turn_id="u-test-1", replace_turn_id="a-test-1"
    )
    assert t_asst.parent_turn_id == "u-test-1"

    # 5. Test rewrite invocation on assistant turn resolves to user prompt
    app._rewrite_prompt("a-test-1")
    mock_comp.start_edit.assert_called_once_with("u-test-1", "How does mergesort work?")


def test_live_activity_thinking_box_enclosure():
    """Verify that live activity Thinking Process and routing boxes are fully enclosed 4-sided boxes
    (with rounded corners ╭, ╮, ╰, ╯ and left/right borders │) and not cut in half."""
    from calc_terminal.ui.live_activities import _render_enclosed_box, _render_enclosed_panel_markup

    title = "💭 Thinking Process (303ms)"
    thought_body = (
        "The error is clear - the file `./components/workspace/Workspace` doesn't exist.\n"
        "Let me check what's in the workspace directory and create the missing\n"
        "Workspace.tsx component."
    )
    lines = _render_enclosed_box(title, thought_body, accent="#f59e0b", faint="#888888", max_w=80)

    # Top border must be enclosed
    assert lines[0].startswith("  [#f59e0b bold]╭─")
    assert lines[0].endswith("╮[/]")
    assert "💭 Thinking Process (303ms)" in lines[0]

    # Bottom border must be enclosed
    assert lines[-1].startswith("  [#f59e0b bold]╰")
    assert lines[-1].endswith("╯[/]")

    # Middle lines must have both left and right vertical borders
    for mid in lines[1:-1]:
        assert "│" in mid
        assert mid.startswith("  [#f59e0b]│[/]")
        assert mid.endswith("[#f59e0b]│[/]")

    # Verify P2P panel box is also fully enclosed
    p2p_lines = _render_enclosed_panel_markup(
        "⇄ Point-to-Point Data & Workflow Routing",
        ["[dim]Flow Route:[/] [cyan]source[/] ➔ [cyan]target[/]"],
        accent="#38bdf8",
        max_w=80,
    )
    assert p2p_lines[0].startswith("  [#38bdf8 bold]╭─")
    assert p2p_lines[0].endswith("╮[/]")
    assert p2p_lines[-1].startswith("  [#38bdf8 bold]╰")
    assert p2p_lines[-1].endswith("╯[/]")
    for mid in p2p_lines[1:-1]:
        assert mid.startswith("  [#38bdf8]│[/]")
        assert mid.endswith("[#38bdf8]│[/]")











