"""
Tests for Low-End PC Optimization, Eco Mode, Hardware Analyzer Caching, and FS Watcher Noise Filtering.
"""

import os
import unittest

from calc_terminal.hardware_analyzer import (
    HardwareAnalyzer,
    HardwareProfile,
    CPUInfo,
    RAMInfo,
    GPUInfo,
)
from calc_terminal.fs_watcher import WorkspaceWatcher, _Handler, IGNORED_DIRS, is_ignored_path
from calc_terminal.config import CCTConfig, load_config


class TestLowEndOptimization(unittest.TestCase):
    def test_hardware_profile_roundtrip(self):
        prof = HardwareAnalyzer.analyze()
        self.assertIsInstance(prof, HardwareProfile)
        d = prof.to_dict()
        prof2 = HardwareProfile.from_dict(d)
        self.assertEqual(prof.cpu_threads, prof2.cpu_threads)
        self.assertEqual(prof.ram_total_gb, prof2.ram_total_gb)
        self.assertEqual(prof.gpu_name, prof2.gpu_name)

    def test_is_low_end_detection(self):
        # Low-end profile: 2 threads, 4GB RAM
        low_prof = HardwareProfile(
            cpu=CPUInfo(model="Celeron", physical_cores=2, logical_cores=2),
            ram=RAMInfo(total_gb=4.0, available_gb=1.5),
            gpu=GPUInfo(detected=True, name="Intel UHD Graphics 600", backend="CPU"),
        )
        self.assertTrue(HardwareAnalyzer.is_low_end(low_prof))

        # High-end profile: 16 threads, 32GB RAM, discrete GPU
        high_prof = HardwareProfile(
            cpu=CPUInfo(model="Core i7", physical_cores=8, logical_cores=16),
            ram=RAMInfo(total_gb=32.0, available_gb=20.0),
            gpu=GPUInfo(detected=True, name="NVIDIA GeForce RTX 4080", vram_total_gb=16.0, backend="CUDA"),
        )
        self.assertFalse(HardwareAnalyzer.is_low_end(high_prof))

    def test_hardware_analyzer_cache(self):
        # Second call to analyze should hit the disk cache
        prof1 = HardwareAnalyzer.analyze()
        prof2 = HardwareAnalyzer.analyze()
        self.assertEqual(prof1.cpu_model, prof2.cpu_model)
        self.assertEqual(prof1.gpu_name, prof2.gpu_name)

    def test_fs_watcher_ignored_dirs(self):
        self.assertIn(".git", IGNORED_DIRS)
        self.assertIn("node_modules", IGNORED_DIRS)
        self.assertIn("__pycache__", IGNORED_DIRS)

        self.assertTrue(is_ignored_path(r"C:\project\.git\index"))
        self.assertTrue(is_ignored_path(r"C:\project\node_modules\pkg\file.js"))
        self.assertTrue(is_ignored_path(r"C:\project\.venv\Lib\site.py"))
        self.assertFalse(is_ignored_path(r"C:\project\src\main.py"))

        # Handler should filter out events in ignored dirs
        reported = []
        class DummyWatcher:
            def report(self, path):
                reported.append(path)

        handler = _Handler(DummyWatcher())
        handler._emit(r"C:\project\.git\index")
        handler._emit(r"C:\project\node_modules\pkg\file.js")
        handler._emit(r"C:\project\src\main.py")

        self.assertEqual(len(reported), 1)
        self.assertIn("main.py", reported[0])

    def test_config_eco_mode_and_env(self):
        cfg = CCTConfig()
        self.assertTrue(hasattr(cfg, "eco_mode"))
        self.assertTrue(hasattr(cfg, "low_end_device_optimization"))

        # Test environment variable override
        old_env = os.environ.get("CAT_ECO_MODE")
        try:
            os.environ["CAT_ECO_MODE"] = "1"
            import calc_terminal.config as c_mod
            c_mod._cached = None
            cfg_loaded = c_mod.load_config()
            self.assertTrue(cfg_loaded.eco_mode)

            os.environ["CAT_ECO_MODE"] = "0"
            c_mod._cached = None
            cfg_loaded_off = c_mod.load_config()
            self.assertFalse(cfg_loaded_off.eco_mode)
        finally:
            if old_env is not None:
                os.environ["CAT_ECO_MODE"] = old_env
            else:
                os.environ.pop("CAT_ECO_MODE", None)


if __name__ == "__main__":
    unittest.main()
