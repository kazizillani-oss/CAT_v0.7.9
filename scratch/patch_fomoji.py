import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('calc_terminal/fomoji_manager.py', 'r', encoding='utf-8') as f:
    text = f.read().replace('\r\n', '\n')

snippet = '''
_FOMOJI_RUNTIME_STATE: Dict[str, Any] = {
    "status": "idle",
    "running": False,
    "ready": False,
    "port": 3000,
    "step": "",
    "progress": 0.0,
}

def get_fomoji_runtime_state() -> Dict[str, Any]:
    global _FOMOJI_RUNTIME_STATE
    return dict(_FOMOJI_RUNTIME_STATE)

def update_fomoji_runtime_state(**kwargs) -> Dict[str, Any]:
    global _FOMOJI_RUNTIME_STATE
    _FOMOJI_RUNTIME_STATE.update(kwargs)
    return dict(_FOMOJI_RUNTIME_STATE)

class CLIProgressAnimation:
    def __init__(self, title: str = "", bar_width: int = 20, enabled: bool = True):
        self.title = title
        self.bar_width = bar_width
        self.enabled = enabled
        self._progress = 0.0
        self._running = False

    def _render_bar(self, progress: float) -> str:
        progress = max(0.0, min(1.0, progress))
        filled_len = int(round(self.bar_width * progress))
        empty_len = self.bar_width - filled_len
        percent = int(round(progress * 100))
        bar = "█" * filled_len + "░" * empty_len
        return f"{bar} {percent}%"

    def start(self):
        self._running = True

    def update(self, title: Optional[str] = None, progress: Optional[float] = None):
        if title is not None:
            self.title = title
        if progress is not None:
            self._progress = progress

    def finish(self, success: bool = True, message: Optional[str] = None):
        self._running = False
        icon = "✓" if success else "✗"
        msg = message or self.title
        sys.stdout.write(f"{icon} {msg}\\n")
        sys.stdout.flush()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.finish(success=False, message=str(exc_val) or self.title)
        else:
            self.finish(success=True, message=self.title)

def start_fomoji_server_background(server_dir: Optional[Path] = None, node_path: Optional[str] = None) -> None:
    import threading
    def _run():
        try:
            start_fomoji_server(server_dir=server_dir, node_path=node_path)
        except Exception:
            pass
    t = threading.Thread(target=_run, daemon=True)
    t.start()
'''

if 'get_fomoji_runtime_state' not in text:
    idx = text.find('class NodeEnvironment:')
    assert idx != -1
    text = text[:idx] + snippet + '\n' + text[idx:]

# Also update start_fomoji_server signature to accept progress_anim
old_sig = 'def start_fomoji_server(\n    server_dir: Path,\n    node_path: str,\n    timeout: int = 35,\n) -> Tuple[bool, str]:'
new_sig = 'def start_fomoji_server(\n    server_dir: Path,\n    node_path: str,\n    timeout: int = 35,\n    progress_anim: Optional[Any] = None,\n) -> Tuple[bool, str]:'
if old_sig in text:
    text = text.replace(old_sig, new_sig, 1)

# In start_fomoji_server, notify progress_anim if provided
check_loop = 'for _ in range(timeout * 2):\n        if check_server_reachable(port=port):'
new_check_loop = '''for _ in range(timeout * 2):
        if progress_anim:
            try:
                progress_anim.update(title=f"Starting Fomoji server on port {port}...", progress=0.75)
            except Exception:
                pass
        if check_server_reachable(port=port):'''
if check_loop in text:
    text = text.replace(check_loop, new_check_loop, 1)

# In initialize_fomoji_subsystem, add background and animate params
old_init = 'def initialize_fomoji_subsystem(interactive: bool = True) -> bool:'
new_init = '''def initialize_fomoji_subsystem(interactive: bool = True, background: bool = False, animate: bool = True) -> bool:
    if background:
        start_fomoji_server_background()
        return True'''
if old_init in text:
    text = text.replace(old_init, new_init, 1)

with open('calc_terminal/fomoji_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('SUCCESS: patched fomoji_manager.py')

