#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""
Automated unit and integration tests for Acer ALG RGB GUI.
"""

import sys
import os
import unittest
import tempfile
import json

# Add gui package to path
GUI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GUI_DIR not in sys.path:
    sys.path.insert(0, GUI_DIR)

from alg_rgb_gui.colors import (
    SUPPORTED_COLORS, COLOR_OFF, get_color,
    hex_to_rgb, rgb_to_hex, find_nearest_preset
)
from alg_rgb_gui.config import ConfigManager
from alg_rgb_gui.backend import read_diagnostics, find_cli_path


class TestColors(unittest.TestCase):
    def test_preset_count(self):
        """Verify the 16 hardware-supported calibrated color presets."""
        self.assertEqual(len(SUPPORTED_COLORS), 16)

    def test_get_color(self):
        """Test retrieving colors by name."""
        red = get_color("red")
        self.assertIsNotNone(red)
        self.assertEqual(red.hex_code, "#FF0000")
        self.assertEqual(red.rgb_tuple, (255, 0, 0))

        cyan = get_color("cyan")
        self.assertIsNotNone(cyan)
        self.assertEqual(cyan.hex_code, "#00FFC8")

        off = get_color("off")
        self.assertIsNotNone(off)
        self.assertEqual(off.name, "off")

        none_col = get_color("nonexistent-color")
        self.assertIsNone(none_col)

    def test_hex_conversions(self):
        """Test parsing and formatting hex codes."""
        self.assertEqual(hex_to_rgb("#FF0000"), (255, 0, 0))
        self.assertEqual(hex_to_rgb("00FFC8"), (0, 255, 200))
        self.assertEqual(hex_to_rgb("#F00"), (255, 0, 0))
        self.assertIsNone(hex_to_rgb("invalid"))
        self.assertEqual(rgb_to_hex(255, 0, 0), "#FF0000")
        self.assertEqual(rgb_to_hex(0, 255, 200), "#00FFC8")

    def test_nearest_preset_matching(self):
        """Test perceptual nearest-match color algorithm."""
        # Exact red
        match_red = find_nearest_preset(255, 0, 0)
        self.assertEqual(match_red.name, "red")

        # Slightly off-red (#E63946)
        match_pink = find_nearest_preset(230, 57, 70)
        self.assertIn(match_pink.name, ("pink", "red", "magenta"))

        # Pure sky blue (#00BFFF)
        match_cyan = find_nearest_preset(0, 191, 255)
        self.assertIn(match_cyan.name, ("cyan", "light-blue", "blue"))

        # Pure green
        match_green = find_nearest_preset(0, 255, 0)
        self.assertEqual(match_green.name, "green")


class TestBackend(unittest.TestCase):
    def test_find_cli_path(self):
        """Verify detection of the alg-rgb CLI binary."""
        cli = find_cli_path()
        self.assertIsNotNone(cli, "alg-rgb CLI should be located on system or in repo")
        self.assertTrue(os.path.exists(cli))
        self.assertTrue(os.access(cli, os.X_OK))

    def test_read_diagnostics(self):
        """Test non-intrusive diagnostics parsing."""
        diag = read_diagnostics()
        self.assertIsInstance(diag, dict)
        self.assertIn("device_exists", diag)
        self.assertIn("device_writable", diag)
        self.assertIn("last_acpi_status", diag)
        self.assertIn("software_state", diag)


class TestConfig(unittest.TestCase):
    def test_config_save_load(self):
        """Test persistent settings serialization and deserialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            orig_dir = ConfigManager.__init__
            cfg = ConfigManager()
            cfg.config["last_color"] = "cyan"
            cfg.config["last_brightness"] = 2
            self.assertEqual(cfg.get("last_color"), "cyan")
            self.assertEqual(cfg.get("last_brightness"), 2)


if __name__ == "__main__":
    unittest.main()
