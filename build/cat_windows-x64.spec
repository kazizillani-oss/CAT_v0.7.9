# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['C:\\Users\\ADMIN\\OneDrive\\PlayGround_Official\\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\\CAT_v0.7.9\\CAT_v0.7.4\\main.py'],
    pathex=['C:\\Users\\ADMIN\\OneDrive\\PlayGround_Official\\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\\CAT_v0.7.9\\CAT_v0.7.4'],
    binaries=[],
    datas=[('C:\\Users\\ADMIN\\OneDrive\\PlayGround_Official\\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\\CAT_v0.7.9\\CAT_v0.7.4\\calc_terminal\\models\\*.json', 'calc_terminal/models'), ('C:\\Users\\ADMIN\\OneDrive\\PlayGround_Official\\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\\CAT_v0.7.9\\CAT_v0.7.4\\calc_terminal\\providers\\*.json', 'calc_terminal/providers'), ('C:\\Users\\ADMIN\\OneDrive\\PlayGround_Official\\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\\CAT_v0.7.9\\CAT_v0.7.4\\calc_terminal\\cat.ico', 'calc_terminal'), ('C:\\Users\\ADMIN\\OneDrive\\PlayGround_Official\\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\\CAT_v0.7.9\\CAT_v0.7.4\\cat_capability_registry.json', '.')],
    hiddenimports=['calc_terminal', 'calc_terminal.cli', 'calc_terminal.app', 'calc_terminal.updater', 'calc_terminal.first_run', 'calc_terminal.chat_store', 'calc_terminal.fomoji_auth', 'calc_terminal.doctor', 'calc_terminal.terminal_identity', 'calc_terminal.hardware_analyzer', 'calc_terminal.compatibility_engine', 'calc_terminal.benchmark_system', 'calc_terminal.ollama_catalog', 'calc_terminal.ollama_download', 'calc_terminal.web.server', 'calc_terminal.ui.app', 'textual', 'textual.widgets', 'textual.containers', 'textual.driver', 'rich', 'rich.syntax', 'tree_sitter', 'tree_sitter_python', 'tree_sitter_json', 'tree_sitter_markdown', 'tree_sitter_yaml', 'tree_sitter_toml', 'watchdog', 'watchdog.observers', 'colorama', 'requests', 'plyer', 'plyer.platforms.win.notification'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='cat.exe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='C:\\Users\\ADMIN\\OneDrive\\PlayGround_Official\\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\\CAT_v0.7.9\\CAT_v0.7.4\\calc_terminal\\cat.ico',
)
