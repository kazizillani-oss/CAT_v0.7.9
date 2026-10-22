"""
_probe_cat_fatty_full_parity.py
Automated 15-Dimension Parity Audit and Verification Probe for CAT ↔ Fatty CAT
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure root of repo is in sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from calc_terminal.web.server import app
from calc_terminal import (
    chat_store,
    mcp,
    theme,
    extensions as cct_ext,
    fomoji_auth,
    identity,
    ai_personalization as ap,
    customization as cust,
    aicore,
    eventbus,
    workspace,
    memory,
)
from calc_terminal.ui import theme_css, header as cct_header, welcome_modal
from calc_terminal.gestures import manager as gestures_mgr
from calc_terminal.providers import provider_manager as pm

client = TestClient(app)

class TestCatFattyFullParity(unittest.TestCase):

    def test_dimension_01_main_menu_structure(self):
        """Dimension 1: Main Menu Endpoint matches CAT CLI header.py"""
        resp = client.get("/api/menu")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)
        self.assertIn("downloaded_count", data)

        actions = [item["action"] for item in data["items"] if not item.get("is_separator")]
        # Must include all base navigation items
        expected_base = [
            "open_folder",
            "recent_workspaces",
            "chats",
            "mcp_servers",
            "backup_providers",
            "themes",
            "extensions",
            "user",
            "signout",
        ]
        for b in expected_base:
            self.assertIn(b, actions, f"Missing base nav item: {b}")

    def test_dimension_02_filesystem_browse_and_validate(self):
        """Dimension 2: Method A (Browse) and Method B (Validate)"""
        # Method A: Browse
        resp = client.get("/api/fs/browse")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("current_path", data)
        self.assertIn("folders", data)
        self.assertIn("drives", data)

        # Method B: Validate valid path
        valid_dir = os.path.abspath(str(repo_root))
        resp2 = client.get(f"/api/fs/validate?path={valid_dir}")
        self.assertEqual(resp2.status_code, 200)
        d2 = resp2.json()
        self.assertTrue(d2["valid"])

        # Method B: Validate invalid path
        resp3 = client.get("/api/fs/validate?path=C:\\nonexistent_invalid_path_xyz123")
        self.assertEqual(resp3.status_code, 200)
        d3 = resp3.json()
        self.assertFalse(d3["valid"])

    def test_dimension_03_workspace_open_and_recent(self):
        """Dimension 3: Workspace open, recent list, pin, and remove"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Open workspace
            resp = client.post("/api/workspace/open", json={"path": tmpdir})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["path"], os.path.abspath(tmpdir))

            # Query recent
            resp_rec = client.get("/api/workspace/recent")
            self.assertEqual(resp_rec.status_code, 200)
            workspaces = resp_rec.json()["workspaces"]
            paths = [w["path"] for w in workspaces]
            self.assertIn(os.path.abspath(tmpdir), paths)

            # Pin workspace
            resp_pin = client.post("/api/workspace/recent/pin", json={"path": os.path.abspath(tmpdir), "pinned": True})
            self.assertEqual(resp_pin.status_code, 200)

            # Remove workspace
            resp_rem = client.post("/api/workspace/recent/remove", json={"path": os.path.abspath(tmpdir)})
            self.assertEqual(resp_rem.status_code, 200)

    def test_dimension_04_chats_crud_and_persistence(self):
        """Dimension 4: Real chats persistence in ~/.cat/chats/"""
        # Create chat
        cname = "Test Parity Chat Session"
        resp = client.post("/api/chats", json={"name": cname})
        self.assertEqual(resp.status_code, 200)
        chat_id = resp.json()["id"]
        self.assertTrue(chat_id)

        # List chats
        resp_list = client.get("/api/chats")
        self.assertEqual(resp_list.status_code, 200)
        ids = [c["id"] for c in resp_list.json()["chats"]]
        self.assertIn(chat_id, ids)

        # Get single chat
        resp_get = client.get(f"/api/chats/{chat_id}")
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.json()["name"], cname)

        # Rename chat
        new_name = "Renamed Parity Chat"
        resp_ren = client.post(f"/api/chats/{chat_id}/rename", json={"name": new_name})
        self.assertEqual(resp_ren.status_code, 200)

        # Delete chat
        resp_del = client.delete(f"/api/chats/{chat_id}")
        self.assertEqual(resp_del.status_code, 200)

    def test_dimension_05_mcp_servers_management(self):
        """Dimension 5: Real MCP server configuration and status"""
        server_data = {
            "id": "test_mcp_server_probe",
            "name": "Test MCP Probe",
            "command": "python",
            "args": ["-c", "print('mcp probe')"],
            "env": {"TEST": "1"}
        }
        # Add server
        resp_add = client.post("/api/mcp/servers", json=server_data)
        self.assertEqual(resp_add.status_code, 200)

        # Get servers
        resp_get = client.get("/api/mcp/servers")
        self.assertEqual(resp_get.status_code, 200)
        servers = resp_get.json()["servers"]
        s_ids = [s["id"] for s in servers]
        self.assertIn("test_mcp_server_probe", s_ids)

        # Remove server
        resp_del = client.delete("/api/mcp/servers/test_mcp_server_probe")
        self.assertEqual(resp_del.status_code, 200)

    def test_dimension_06_backup_providers_failover_chain(self):
        """Dimension 6: Backup providers chain load and save"""
        resp_get = client.get("/api/backup-providers")
        self.assertEqual(resp_get.status_code, 200)
        original_providers = resp_get.json()["providers"]

        # Save re-ordered chain
        test_chain = ["groq", "openai", "deepseek"]
        resp_save = client.post("/api/backup-providers", json={"providers": test_chain})
        self.assertEqual(resp_save.status_code, 200)
        saved_names = [p.get("provider") for p in resp_save.json()["providers"]]
        for t in test_chain:
            self.assertIn(t, saved_names)

        # Restore original chain
        client.post("/api/backup-providers", json={"providers": original_providers})

    def test_dimension_07_real_provider_failover_simulation(self):
        """Dimension 7: Simulation of aicore failover chain mechanics"""
        orig_resp = client.get("/api/backup-providers")
        orig = orig_resp.json()["providers"]

        primary_cfg = {"provider": "failing_primary", "model": "mock-primary"}
        client.post("/api/backup-providers", json={"providers": ["ollama", "groq"]})

        targets = aicore._failover_targets(primary_cfg)
        self.assertTrue(len(targets) >= 1)
        target_provs = [t[0].get("provider") for t in targets]
        # Primary is tested first
        self.assertEqual(target_provs[0], "failing_primary")
        # Backup chain items are prepared after primary
        self.assertIn("ollama", target_provs[1:])

        # Restore original
        client.post("/api/backup-providers", json={"providers": orig})

    def test_dimension_08_themes_and_css_variables(self):
        """Dimension 8: Themes and dynamic Textual CSS variable injection"""
        resp = client.get("/api/themes")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("themes", data)
        self.assertIn("css_variables", data)
        self.assertIn("surface", data["css_variables"])

        # Switch theme
        resp_sel = client.post("/api/themes/select", json={"theme": "tokyo-night"})
        self.assertEqual(resp_sel.status_code, 200)
        self.assertEqual(resp_sel.json()["theme"], "tokyo-night")
        self.assertIn("css_variables", resp_sel.json())

    def test_dimension_09_extensions_lifecycle(self):
        """Dimension 9: Extensions lifecycle operations"""
        # Test toggling / status on a sample extension
        installed = cct_ext.list_installed()
        if installed:
            first_ext = installed[0]["id"]
            # Enable/Disable
            resp_dis = client.post(f"/api/extensions/{first_ext}/disable")
            self.assertEqual(resp_dis.status_code, 200)
            resp_en = client.post(f"/api/extensions/{first_ext}/enable")
            self.assertEqual(resp_en.status_code, 200)

    def test_dimension_10_user_profile_and_auth(self):
        """Dimension 10: User identity and logout endpoint"""
        resp = client.get("/api/user/profile")
        self.assertEqual(resp.status_code, 200)
        prof = resp.json()
        self.assertIn("user", prof)
        self.assertIn("app", prof)
        self.assertEqual(prof["app"]["name"], identity.APP_NAME)
        self.assertEqual(prof["app"]["version"], identity.APP_VERSION)

        # Logout
        resp_out = client.post("/api/auth/logout")
        self.assertEqual(resp_out.status_code, 200)
        self.assertTrue(resp_out.json()["success"])

    def test_dimension_11_startup_and_welcome_lifecycle(self):
        """Dimension 11: Startup modal status and dismiss lifecycle"""
        resp = client.get("/api/startup/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("version", data)
        self.assertIn("highlights", data)
        self.assertTrue(len(data["highlights"]) > 0)

        # Dismiss
        resp_dis = client.post("/api/startup/dismiss")
        self.assertEqual(resp_dis.status_code, 200)
        self.assertTrue(resp_dis.json()["success"])

    def test_dimension_12_gestures_toggle(self):
        """Dimension 12: Gestures configuration and toggling"""
        resp = client.get("/api/gestures")
        self.assertEqual(resp.status_code, 200)
        gestures = resp.json()["gestures"]
        if gestures:
            gid = gestures[0]["id"]
            resp_tog = client.post("/api/gestures/toggle", json={"id": gid, "enabled": False})
            self.assertEqual(resp_tog.status_code, 200)
            resp_tog2 = client.post("/api/gestures/toggle", json={"id": gid, "enabled": True})
            self.assertEqual(resp_tog2.status_code, 200)

    def test_dimension_13_personalize_and_customization(self):
        """Dimension 13: AI personalization profiles and customization settings"""
        resp = client.get("/api/personalize")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("profiles", data)

        # Switch active profile
        resp_act = client.post("/api/personalize/active", json={"id": "concise"})
        self.assertEqual(resp_act.status_code, 200)

        # Save customization
        resp_sav = client.post("/api/personalize/save", json={
            "id": "concise",
            "prompt": "You are a concise, ultra-precise coding agent.",
            "temperature": 0.5
        })
        self.assertEqual(resp_sav.status_code, 200)

    def test_dimension_14_security_and_path_protection(self):
        """Dimension 14: Protected system folders refusal"""
        # Protected path should be refused
        if sys.platform == "win32":
            prot_dir = "C:\\Windows"
        else:
            prot_dir = "/etc"

        if os.path.exists(prot_dir):
            resp = client.post("/api/workspace/open", json={"path": prot_dir})
            self.assertEqual(resp.status_code, 403)

    def test_dimension_15_chat_persistence_in_agent_api(self):
        """Dimension 15: Chat session persistence when chat_id is passed to /api/chat"""
        # Create session
        new_chat = chat_store.create_chat(name="Agent Persistence Test")
        cid = new_chat["id"]

        # Post chat with chat_id
        resp = client.post("/api/chat", json={
            "message": "Hello CAT core",
            "mode": "build",
            "project_path": str(repo_root),
            "chat_id": cid
        })
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertEqual(d["chat_id"], cid)

        # Verify turns persisted in chat_store
        session = chat_store.get_chat(cid)
        self.assertIsNotNone(session)
        self.assertTrue(len(session.get("turns", session.get("messages", []))) >= 2)

        # Clean up
        chat_store.delete_chat(cid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
