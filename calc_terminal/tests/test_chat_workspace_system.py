"""
Workspace-aware chat store tests — isolation, mode persistence, migration.
"""

import json
import os
import tempfile
import time

import pytest

from calc_terminal import chat_store, ai_modes


@pytest.fixture
def isolated_chats(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        chats_dir = os.path.join(tmp, "chats")
        os.makedirs(chats_dir)
        monkeypatch.setattr(chat_store, "_CHATS_DIR", chats_dir)
        monkeypatch.setattr(chat_store, "_INDEX_FILE", os.path.join(chats_dir, "_index.json"))
        yield chats_dir


def test_path_normalization_windows_style():
    a = chat_store.normalize_workspace_path(r"D:\Projects\Calculator")
    b = chat_store.normalize_workspace_path(r"d:/projects/calculator")
    assert chat_store.paths_equal(a, b)


def test_workspace_isolation(isolated_chats):
    ws_a = os.path.join(isolated_chats, "ProjectA")
    ws_b = os.path.join(isolated_chats, "ProjectB")
    os.makedirs(ws_a)
    os.makedirs(ws_b)

    chat_a = chat_store.create_chat(name="Calc UI", workspace_root=ws_a, created_mode="agent")
    chat_b = chat_store.create_chat(name="Weather app", workspace_root=ws_b, created_mode="research")

    a_list = chat_store.get_chat_summaries(ws_a)
    b_list = chat_store.get_chat_summaries(ws_b)

    assert len(a_list) == 1
    assert len(b_list) == 1
    assert a_list[0]["id"] == chat_a["id"]
    assert b_list[0]["id"] == chat_b["id"]
    assert a_list[0]["created_mode"] == "agent"
    assert b_list[0]["created_mode"] == "research"


def test_mode_persisted_on_turns(isolated_chats):
    ws = os.path.join(isolated_chats, "proj")
    os.makedirs(ws)
    chat = chat_store.create_chat(workspace_root=ws, created_mode="agent")
    snap = ai_modes.snapshot("agent")
    chat_store.add_turn(
        chat["id"], "user", "Build calculator UI",
        mode="agent", mode_snapshot=snap,
    )
    loaded = chat_store.get_chat(chat["id"])
    turn = loaded["turns"][0]
    assert turn["mode"] == "agent"
    assert turn["mode_snapshot"]["accent_hex"] == snap["accent_hex"]
    assert loaded["current_mode"] == "agent"


def test_legacy_migration_unassigned(isolated_chats):
    legacy_id = "legacy002"
    legacy_path = os.path.join(isolated_chats, f"{legacy_id}.json")
    legacy = {
        "id": legacy_id,
        "name": "Old chat",
        "created_at": time.time(),
        "updated_at": time.time(),
        "turn_count": 1,
        "project_path": "",
        "turns": [{"role": "user", "content": "hello", "timestamp": time.time()}],
    }
    with open(legacy_path, "w", encoding="utf-8") as f:
        json.dump(legacy, f)
        f.flush()
        os.fsync(f.fileno())
    with open(chat_store._INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump([{"id": legacy_id, "name": "Old chat", "project_path": ""}], f)

    loaded = chat_store.get_chat(legacy_id)
    assert loaded is not None
    assert loaded["legacy_unassigned"] is True
    assert loaded["schema_version"] == 2
    assert loaded["created_mode"] == "notebook"


def test_group_by_workspace(isolated_chats):
    ws_a = os.path.join(isolated_chats, "A")
    ws_b = os.path.join(isolated_chats, "B")
    os.makedirs(ws_a)
    os.makedirs(ws_b)
    chat_store.create_chat(name="A1", workspace_root=ws_a)
    chat_store.create_chat(name="A2", workspace_root=ws_a)
    chat_store.create_chat(name="B1", workspace_root=ws_b)
    groups = chat_store.group_chats_by_workspace(chat_store.get_chat_summaries())
    assert len(groups) == 2
    keys = {g["workspace_root"] for g in groups}
    assert ws_a in keys
    assert ws_b in keys


def test_search_scoped_to_workspace(isolated_chats):
    ws_a = os.path.join(isolated_chats, "A")
    ws_b = os.path.join(isolated_chats, "B")
    os.makedirs(ws_a)
    os.makedirs(ws_b)
    chat_store.create_chat(name="Calculator UI", workspace_root=ws_a)
    chat_store.create_chat(name="Calculator docs", workspace_root=ws_b)
    results = chat_store.search_chats("Calculator", workspace_root=ws_a, scope="current")
    assert len(results) == 1
    assert chat_store.paths_equal(results[0]["workspace_root"], ws_a)


def test_pin_and_recent(isolated_chats):
    ws = os.path.join(isolated_chats, "proj")
    os.makedirs(ws)
    c1 = chat_store.create_chat(name="One", workspace_root=ws)
    c2 = chat_store.create_chat(name="Two", workspace_root=ws)
    chat_store.pin_chat(c1["id"], True)
    chat_store.touch_last_opened(c2["id"])
    pinned = chat_store.get_pinned_chats()
    recent = chat_store.get_recent_chats(limit=5, workspace_root=ws)
    assert any(p["id"] == c1["id"] for p in pinned)
    assert recent[0]["id"] == c2["id"]


def test_export_markdown(isolated_chats):
    ws = os.path.join(isolated_chats, "proj")
    os.makedirs(ws)
    chat = chat_store.create_chat(name="Export me", workspace_root=ws, created_mode="plan")
    chat_store.add_turn(chat["id"], "user", "Create API", mode="plan")
    md = chat_store.export_chat_markdown(chat["id"])
    assert "Export me" in md
    assert "plan" in md.lower()
    assert "Create API" in md


def test_chat_deletion_preserves_workspace_files(isolated_chats):
    """Deleting a chat record must NEVER delete or touch workspace files on disk."""
    ws = os.path.join(isolated_chats, "MyProject")
    os.makedirs(ws, exist_ok=True)
    source_file = os.path.join(ws, "main.py")
    with open(source_file, "w", encoding="utf-8") as f:
        f.write("print('Important workspace source file')\n")
    readme_file = os.path.join(ws, "README.md")
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write("# Project Readme\n")

    chat = chat_store.create_chat(name="Project Chat", workspace_root=ws)
    cid = chat["id"]
    chat_store.add_turn(cid, "user", "Work on main.py")

    # Delete the conversation record
    assert chat_store.delete_chat(cid) is True

    # Chat record and index must be gone
    assert chat_store.get_chat(cid) is None
    summaries = chat_store.get_chat_summaries(workspace_root=ws)
    assert not any(s["id"] == cid for s in summaries)

    # Workspace files and directory must remain 100% intact
    assert os.path.isdir(ws)
    assert os.path.isfile(source_file)
    with open(source_file, "r", encoding="utf-8") as f:
        assert f.read() == "print('Important workspace source file')\n"
    assert os.path.isfile(readme_file)


def test_chats_panel_flat_rows_deduplication_and_hierarchy(isolated_chats):
    """ChatsPanel must organize by workspace, sub-group by date, and have ZERO duplicate chats."""
    from calc_terminal.ui.chats_panel import ChatsPanel

    ws_a = os.path.join(isolated_chats, "ProjectCalc")
    ws_b = os.path.join(isolated_chats, "ProjectGame")
    os.makedirs(ws_a, exist_ok=True)
    os.makedirs(ws_b, exist_ok=True)

    c1 = chat_store.create_chat(name="Calc 1", workspace_root=ws_a, created_mode="agent")
    c2 = chat_store.create_chat(name="Calc 2", workspace_root=ws_a, created_mode="notebook")
    c3 = chat_store.create_chat(name="Game 1", workspace_root=ws_b, created_mode="build")

    # Pin Calc 1
    chat_store.pin_chat(c1["id"], True)

    pinned = chat_store.get_pinned_chats()
    recent = chat_store.get_recent_chats(limit=10)
    all_chats = chat_store.get_chat_summaries()

    panel = ChatsPanel(
        chats=all_chats,
        active_id=c1["id"],
        workspace_root=ws_a,
        pinned=pinned,
        recent=recent,
    )

    # Scope = all to test full hierarchical tree
    panel._scope = "all"
    panel._filter = "all"
    panel._rebuild_flat_rows()

    # Verify zero duplicate chat rows
    chat_row_ids = [rid for (kind, rid, _) in panel._flat_rows if kind == "chat"]
    assert len(chat_row_ids) == len(set(chat_row_ids)), f"Duplicate chat IDs found: {chat_row_ids}"

    # Verify workspace headers exist
    ws_headers = [data for (kind, _, data) in panel._flat_rows if kind in ("ws", "ws_collapsed")]
    assert len(ws_headers) >= 2

    # Verify date headers exist
    date_headers = [data for (kind, _, data) in panel._flat_rows if kind == "date"]
    assert len(date_headers) >= 1
    assert any("Today" in d.get("label", "") for d in date_headers)


def test_chats_panel_clean_filters(isolated_chats):
    """ChatsPanel has clean filters (All, Current, Pinned, Archived) without mode/today clutter."""
    from calc_terminal.ui.chats_panel import ChatsPanel

    ws = os.path.join(isolated_chats, "WorkspaceM")
    os.makedirs(ws, exist_ok=True)

    c1 = chat_store.create_chat(name="Task 1", workspace_root=ws)
    c2 = chat_store.create_chat(name="Task 2", workspace_root=ws)
    chat_store.pin_chat(c1["id"], True)

    all_chats = chat_store.get_chat_summaries(ws)
    panel = ChatsPanel(chats=all_chats, workspace_root=ws, pinned=[c1])

    # Verify filter list has only the 4 clean filters
    filter_keys = [k for k, _ in panel.FILTERS]
    assert filter_keys == ["all", "current_workspace", "pinned", "archived"]
    assert "today" not in filter_keys
    assert "recent" not in filter_keys
    assert not hasattr(panel, "MODE_FILTERS")

    # Test pinned filter
    panel._filter = "pinned"
    panel._rebuild_flat_rows()
    shown_cids = {rid for (kind, rid, _) in panel._flat_rows if kind == "chat"}
    assert c1["id"] in shown_cids
    assert c2["id"] not in shown_cids


def test_per_conversation_mode_color_snapshots(isolated_chats):
    """Historical turns maintain distinct mode colors without inheriting global mode."""
    ws = os.path.join(isolated_chats, "ModeProj")
    os.makedirs(ws, exist_ok=True)

    chat = chat_store.create_chat(name="Multi Mode Chat", workspace_root=ws, created_mode="agent")
    cid = chat["id"]

    # Turn 1 in Agent mode
    snap_agent = ai_modes.snapshot("agent")
    chat_store.add_turn(cid, "user", "Design agent logic", mode="agent", mode_snapshot=snap_agent)

    # Turn 2 in Research mode
    snap_res = ai_modes.snapshot("research")
    chat_store.add_turn(cid, "user", "Look up paper", mode="research", mode_snapshot=snap_res)

    loaded = chat_store.get_chat(cid)
    turns = loaded["turns"]
    assert len(turns) == 2

    assert turns[0]["mode"] == "agent"
    assert turns[0]["mode_snapshot"]["accent_hex"] == snap_agent["accent_hex"]

    assert turns[1]["mode"] == "research"
    assert turns[1]["mode_snapshot"]["accent_hex"] == snap_res["accent_hex"]

    # Accents must be distinct
    assert turns[0]["mode_snapshot"]["accent_hex"] != turns[1]["mode_snapshot"]["accent_hex"]


def test_confirm_delete_chat_modal():
    """ConfirmDeleteChatModal must confirm file safety and require confirmation."""
    from calc_terminal.ui.nav_screens import ConfirmDeleteChatModal

    modal = ConfirmDeleteChatModal(chat_name="Important conversation")
    assert modal._chat_name == "Important conversation"
    # Verify bindings
    binding_keys = [b.key for b in modal.BINDINGS]
    assert "escape" in binding_keys
    assert "enter" in binding_keys


def test_archive_restore_and_duplicate(isolated_chats):
    """Archiving hides chat from default summaries; duplicating preserves workspace."""
    ws = os.path.join(isolated_chats, "ArchiveProj")
    os.makedirs(ws, exist_ok=True)

    chat = chat_store.create_chat(name="Active Chat", workspace_root=ws, created_mode="plan")
    cid = chat["id"]

    # Archive
    assert chat_store.archive_chat(cid, True) is True
    active_summaries = chat_store.get_chat_summaries(ws)
    assert not any(s["id"] == cid for s in active_summaries)

    archived_summaries = chat_store.filter_chats(
        chat_store.get_chat_summaries(include_archived=True),
        filter_name="archived",
        workspace_root=ws,
    )
    assert any(s["id"] == cid for s in archived_summaries)

    # Restore
    assert chat_store.archive_chat(cid, False) is True
    active_summaries = chat_store.get_chat_summaries(ws)
    assert any(s["id"] == cid for s in active_summaries)

    # Duplicate
    dup = chat_store.duplicate_chat(cid)
    assert dup is not None
    assert dup["id"] != cid
    assert "copy" in dup["name"].lower()
    assert chat_store.paths_equal(dup["workspace_root"], ws)
    assert dup["created_mode"] == "plan"

