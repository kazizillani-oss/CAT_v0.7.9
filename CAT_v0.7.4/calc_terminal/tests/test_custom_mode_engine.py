"""
Tests for Custom Mode Engine & Registry per §2, §3, §55.
"""

import os
import pytest
from calc_terminal.core.mode_registry import ModeRegistry, ModeSpec, ModeBehavior, DEFAULT_MODE_KEYS
from calc_terminal import ai_modes


class TestCustomModeEngine:
    def test_default_modes_cannot_be_overwritten(self, tmp_path):
        reg = ModeRegistry(storage_path=str(tmp_path / "custom_modes.json"))
        for d in DEFAULT_MODE_KEYS:
            ok, err = reg.register_mode(ModeSpec(name=d, description="attempted hijack"))
            assert ok is False
            assert "Cannot overwrite default mode" in err

    def test_default_modes_cannot_be_deleted(self, tmp_path):
        reg = ModeRegistry(storage_path=str(tmp_path / "custom_modes.json"))
        for d in DEFAULT_MODE_KEYS:
            ok, err = reg.unregister_mode(d)
            assert ok is False
            assert "Cannot delete default mode" in err

    def test_create_and_register_biolab_mode(self, tmp_path):
        reg = ModeRegistry(storage_path=str(tmp_path / "custom_modes.json"))
        biolab = ModeSpec(
            name="BioLab",
            description="Autonomous biology lab workflow",
            inherits=["research"],
            capabilities=["blast.search", "ncbi.query", "biopython.parse", "pymol.open"],
            behavior=ModeBehavior(
                planning="high",
                verification="strict",
                citations="required",
                experiment_tracking=True,
            ),
            accent_hex="#10b981",
            icon="🧬",
        )
        ok, msg = reg.register_mode(biolab)
        assert ok is True
        assert "registered successfully" in msg

        # Retrieve
        fetched = reg.get_mode("biolab")
        assert fetched is not None
        assert fetched.name == "BioLab"
        assert fetched.behavior.verification == "strict"
        assert "blast.search" in fetched.capabilities

    def test_mode_name_resolution(self, tmp_path):
        reg = ModeRegistry(storage_path=str(tmp_path / "custom_modes.json"))
        reg.register_mode(ModeSpec(name="QuantumLab", description="Quantum workflows"))

        # Exact and case-insensitive
        assert reg.resolve_mode_name("QuantumLab") == "QuantumLab"
        assert reg.resolve_mode_name("quantumlab") == "QuantumLab"
        assert reg.resolve_mode_name("/quantumlab") == "QuantumLab"

        # Natural language resolution
        assert reg.resolve_mode_name("Please switch to QuantumLab mode") == "QuantumLab"
        assert reg.resolve_mode_name("Use notebook mode") == "notebook"

    def test_export_and_import_mode(self, tmp_path):
        reg = ModeRegistry(storage_path=str(tmp_path / "custom_modes.json"))
        spec = ModeSpec(
            name="MLTrainer",
            description="Deep learning trainer",
            capabilities=["pytorch.train", "ml.detect_hardware"],
        )
        reg.register_mode(spec)

        export_path = str(tmp_path / "mltrainer.json")
        ok_exp, msg_exp = reg.export_mode("MLTrainer", export_path)
        assert ok_exp is True
        assert os.path.exists(export_path)

        # Import into clean registry
        reg2 = ModeRegistry(storage_path=str(tmp_path / "custom_modes2.json"))
        ok_imp, msg_imp = reg2.import_mode(export_path)
        assert ok_imp is True
        assert reg2.get_mode("mltrainer") is not None

    def test_custom_mode_syncs_with_ai_modes(self, tmp_path):
        reg = ModeRegistry(storage_path=str(tmp_path / "custom_modes.json"))
        reg.register_mode(ModeSpec(name="RoboTester", description="Testing persona", accent_hex="#f43f5e"))

        # Check ai_modes has it
        assert "robotester" in ai_modes.MODE_META
        meta = ai_modes.meta("robotester")
        assert meta["label"] == "RoboTester"
        prompt = ai_modes.system_prompt_for("robotester")
        assert prompt is not None
