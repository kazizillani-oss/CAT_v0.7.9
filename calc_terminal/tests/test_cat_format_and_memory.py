"""Tests for proprietary .cat file format, encrypted storage, and first-chat memory recall."""

import json
import os
import shutil
import tempfile
import pytest

from calc_terminal import cat_format
from calc_terminal import chat_store
from calc_terminal import memory
from calc_terminal import agent


def test_cat_format_magic_header_and_encryption():
    """Verify that .cat format uses the proprietary magic header and encrypts payload."""
    payload = {
        "user": "developer",
        "secret_keys": ["cat-key-1234"],
        "prompt": "Create a 3D interactive portfolio",
        "nested": {"turn_id": 1, "active": True},
    }

    sealed = cat_format.seal_cat_data(payload)
    # Must start with proprietary CAT header
    assert sealed.startswith(cat_format.CAT_HEADER)
    assert sealed.startswith(cat_format.MAGIC_HEADER)
    # The plain text json should not appear in raw sealed bytes
    assert b"Create a 3D interactive portfolio" not in sealed
    assert b"cat-key-1234" not in sealed

    # Unseal recovers exact data
    unsealed = cat_format.unseal_cat_data(sealed)
    assert unsealed == payload


def test_cat_format_tamper_and_invalid_header_rejection():
    """Verify that outside tampering or wrong header are rejected."""
    # Strict mode without magic header raises ValueError
    with pytest.raises(ValueError, match="Invalid CAT secure container"):
        cat_format.unseal_cat_data(b'{"plain": "json_data"}', allow_legacy_json=False)

    # Tampered payload with valid header
    fake_cat = cat_format.CAT_HEADER + b"corrupted_encrypted_bytes_here_12345678"
    with pytest.raises(ValueError):
        cat_format.unseal_cat_data(fake_cat)


def test_cat_format_file_save_and_load(tmp_path):
    """Verify save_cat_file and load_cat_file file operations."""
    target_file = tmp_path / "user_data.cat"
    data = {"project": "CAT Portfolio", "version": "0.7.9", "stars": 9999}

    cat_format.save_cat_file(str(target_file), data)
    assert target_file.exists()

    # Raw bytes check
    raw_content = target_file.read_bytes()
    assert raw_content.startswith(cat_format.CAT_HEADER)
    assert b"CAT Portfolio" not in raw_content

    # Load back
    loaded = cat_format.load_cat_file(str(target_file))
    assert loaded == data


def _setup_isolated_chat_store(tmp_path, monkeypatch):
    store_dir = str(tmp_path / "chats")
    os.makedirs(store_dir, exist_ok=True)
    monkeypatch.setattr(chat_store, "_CHATS_DIR", store_dir)
    monkeypatch.setattr(chat_store, "_INDEX_FILE", os.path.join(store_dir, "_index.cat"))
    monkeypatch.setattr(chat_store, "_LEGACY_INDEX_FILE", os.path.join(store_dir, "_index.json"))
    return store_dir


def test_chat_store_cat_storage(tmp_path, monkeypatch):
    """Verify chat_store saves chats and index in .cat format."""
    store_dir = _setup_isolated_chat_store(tmp_path, monkeypatch)

    # Create new chat
    chat = chat_store.create_chat(name="Test Conversation", workspace_root=str(tmp_path))
    chat_id = chat["id"]
    chat_store.add_turn(chat_id, "user", "Hello CAT, please remember my portfolio!")
    chat_store.add_turn(chat_id, "assistant", "I will remember your portfolio forever.")

    # Verify .cat files created
    index_cat = os.path.join(store_dir, "_index.cat")
    chat_cat = os.path.join(store_dir, f"{chat_id}.cat")
    assert os.path.exists(index_cat)
    assert os.path.exists(chat_cat)

    # Confirm raw files are encrypted with CAT_HEADER
    with open(index_cat, "rb") as f:
        assert f.read().startswith(cat_format.CAT_HEADER)
    with open(chat_cat, "rb") as f:
        assert f.read().startswith(cat_format.CAT_HEADER)

    # Reload chat
    retrieved = chat_store.get_chat(chat_id)
    assert retrieved is not None
    assert retrieved["name"] == "Test Conversation"
    assert len(retrieved["turns"]) == 2
    assert retrieved["turns"][0]["content"] == "Hello CAT, please remember my portfolio!"


def test_chat_store_legacy_json_migration(tmp_path, monkeypatch):
    """Verify automatic non-destructive migration from legacy .json to .cat."""
    store_dir = _setup_isolated_chat_store(tmp_path, monkeypatch)

    # Write legacy json chat
    legacy_chat = {
        "id": "legacy-chat-001",
        "name": "Legacy Project Chat",
        "version": 1,
        "created_at": 1600000000,
        "updated_at": 1600000100,
        "turns": [
            {"id": "t1", "role": "user", "content": "Initial legacy prompt", "timestamp": 1600000010},
            {"id": "t2", "role": "assistant", "content": "Initial legacy response", "timestamp": 1600000020},
        ],
    }
    legacy_json_path = os.path.join(store_dir, "legacy-chat-001.json")
    with open(legacy_json_path, "w", encoding="utf-8") as f:
        json.dump(legacy_chat, f)

    # Access via chat_store
    retrieved = chat_store.get_chat("legacy-chat-001")
    assert retrieved is not None
    assert retrieved["name"] == "Legacy Project Chat"
    assert len(retrieved["turns"]) == 2

    # Verify migrated to .cat format
    migrated_cat_path = os.path.join(store_dir, "legacy-chat-001.cat")
    assert os.path.exists(migrated_cat_path)
    with open(migrated_cat_path, "rb") as f:
        assert f.read().startswith(cat_format.CAT_HEADER)


def test_get_first_chat_and_cross_chat_memory_context(tmp_path, monkeypatch):
    """Verify that get_first_chat retrieves the very first chat and build_cross_chat_memory_context injects it."""
    store_dir = _setup_isolated_chat_store(tmp_path, monkeypatch)

    # Create first foundational chat
    c1 = chat_store.create_chat(name="Genesis Chat", workspace_root=str(tmp_path))
    c1_id = c1["id"]
    chat_store.add_turn(c1_id, "user", "We are building a cyber-themed 3D portfolio with Three.js and Vite.")
    chat_store.add_turn(c1_id, "assistant", "Understood. We will structure the portfolio with 3D canvas, hero, and sleek dark aesthetic.")

    # Create subsequent chat
    c2 = chat_store.create_chat(name="Second Session", workspace_root=str(tmp_path))
    c2_id = c2["id"]
    chat_store.add_turn(c2_id, "user", "Add sound effects to buttons.")
    chat_store.add_turn(c2_id, "assistant", "Sound effects added.")

    # Test get_first_chat
    first = chat_store.get_first_chat(workspace_root=str(tmp_path))
    assert first is not None
    assert first["id"] == c1_id
    assert "Genesis Chat" in first["name"]

    # Test build_cross_chat_memory_context
    ctx = chat_store.build_cross_chat_memory_context(workspace_root=str(tmp_path), current_chat_id=c2_id)
    assert "VERY FIRST CONVERSATION" in ctx
    assert "Genesis Chat" in ctx
    assert "We are building a cyber-themed 3D portfolio" in ctx
    assert "PREVIOUS CONVERSATIONS" in ctx
    assert ".cat Secure Storage" in ctx


def test_memory_vault_cat_migration(tmp_path, monkeypatch):
    """Verify user memory uses user_memory.cat and migrates smoothly."""
    mem_file = os.path.join(str(tmp_path), "user_memory.cat")
    legacy_file = os.path.join(str(tmp_path), ".cct_memory.json")
    monkeypatch.setattr(memory, "MEMORY_FILE", mem_file)
    monkeypatch.setattr(memory, "LEGACY_MEMORY_FILE", legacy_file)

    # Save memory
    memory.add_fact("User prefers sleek dark mode with glassmorphism")
    assert os.path.exists(mem_file)
    with open(mem_file, "rb") as f:
        assert f.read().startswith(cat_format.CAT_HEADER)

    # Check context_block
    ctx = memory.context_block(query="portfolio dark mode")
    assert "User prefers sleek dark mode" in ctx


def test_agent_history_retention_and_directives(monkeypatch):
    """Verify run_agent respects conversation history and injects web application directive."""
    captured_prompts = []
    captured_sys_prompt = []

    def mock_query_ai(prompt, **kwargs):
        captured_sys_prompt.append(kwargs.get("system_prompt", ""))
        captured_prompts.append(prompt)
        return "I have reviewed the portfolio code and App.tsx is properly configured."

    from calc_terminal import aicore
    monkeypatch.setattr(aicore, "query_ai", mock_query_ai)

    history = [
        ("user", "We are creating a 3D portfolio app."),
        ("assistant", "I will help build it with Vite and Three.js."),
    ]

    final_text, steps, meta = agent.run_agent(
        "Please check if App.tsx is ready for preview",
        history=history,
        max_steps=1,
    )

    # Verify history is preserved in convo prompt
    assert any("We are creating a 3D portfolio app." in p for p in captured_prompts)
    assert any("I will help build it with Vite and Three.js." in p for p in captured_prompts)
    # Verify directive is present in system prompt
    assert any("WEB APPLICATION & PREVIEW DIRECTIVE" in sp for sp in captured_sys_prompt)
    assert "App.tsx" in final_text
