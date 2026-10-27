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
from alg_rgb_gui.sensors import SensorEngine
from alg_rgb_gui.thermal_graph import TemperatureHistoryGraph


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


class TestSensors(unittest.TestCase):
    def test_sensor_engine_reading(self):
        """Test read-only sensor telemetry gathering."""
        engine = SensorEngine()
        cpu = engine.read_cpu_telemetry()
        self.assertIsInstance(cpu.package_temp, float)
        self.assertTrue(cpu.sensor_found)
        self.assertGreater(len(cpu.cores), 0)

        gpu = engine.read_gpu_telemetry()
        self.assertIsInstance(gpu.available, bool)
        if gpu.available:
            self.assertGreaterEqual(gpu.temp_c, 0.0)

        aux = engine.read_auxiliary_temperatures()
        self.assertIsInstance(aux, dict)

        fan_status = engine.get_fan_hardware_status()
        self.assertEqual(fan_status.mode, "Firmware Automatic (EC Managed)")
        self.assertFalse(fan_status.manual_control_supported)


class TestThermalGraph(unittest.TestCase):
    def test_graph_data_accumulation(self):
        """Test rolling queue point accumulation."""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        graph = TemperatureHistoryGraph(max_points=30)
        graph.add_sample(65.0, 50.0)
        self.assertEqual(graph.last_cpu, 65.0)
        self.assertEqual(graph.last_gpu, 50.0)
        self.assertEqual(len(graph.history), 30)

    def test_graph_render(self):
        """Verify graph renders cleanly without TypeError on drawText overloads."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QImage, QPainter
        app = QApplication.instance() or QApplication([])
        graph = TemperatureHistoryGraph(max_points=30)
        graph.resize(450, 160)
        graph.add_sample(82.4, 55.7)

        img = QImage(450, 160, QImage.Format.Format_ARGB32)
        painter = QPainter(img)
        graph.render(painter)
        painter.end()


class TestFanDashboard(unittest.TestCase):
    def test_hardware_report_content(self):
        """Verify hardware report markdown includes vital ACPI and EC details."""
        from alg_rgb_gui.fan_dashboard import HardwareReportDialog
        report = HardwareReportDialog._generate_report_markdown()
        self.assertIn("Acer ALG AL15G-52", report)
        self.assertIn("CLV0001:00", report)
        self.assertIn("Embedded Controller", report)
        self.assertIn("hwmon", report)

    def test_thermals_and_fan_widget_ui(self):
        """Verify ThermalsAndFanWidget initialization and mode selection."""
        from PyQt6.QtWidgets import QApplication
        from alg_rgb_gui.fan_dashboard import ThermalsAndFanWidget
        from alg_rgb_gui.fan_controller import FanMode
        from alg_rgb_gui.config import ConfigManager

        app = QApplication.instance() or QApplication([])
        cfg = ConfigManager()
        cfg.config = {
            "fan_mode": "auto",
            "custom_cpu_duty": 50,
            "custom_gpu_duty": 50,
            "sync_fans": True,
        }
        widget = ThermalsAndFanWidget(config=cfg)
        widget.stop_monitoring()  # Stop polling timer for test

        # Check default state
        self.assertEqual(widget.fan_controller.current_mode, FanMode.AUTO)
        self.assertFalse(widget.slider_cpu_fan.isEnabled())
        self.assertFalse(widget.slider_gpu_fan.isEnabled())

        # Switch to Custom mode
        widget.on_mode_selected(FanMode.CUSTOM)
        self.assertEqual(widget.fan_controller.current_mode, FanMode.CUSTOM)
        self.assertTrue(widget.slider_cpu_fan.isEnabled())
        self.assertTrue(widget.slider_gpu_fan.isEnabled())

        # Test Quick preset
        widget.apply_quick_preset(75)
        self.assertEqual(widget.slider_cpu_fan.value(), 75)
        self.assertEqual(widget.slider_gpu_fan.value(), 75)
        self.assertEqual(widget.fan_controller.custom_cpu_duty, 75)

        # Switch to Balanced mode
        widget.on_mode_selected(FanMode.BALANCED)
        self.assertEqual(widget.fan_controller.current_mode, FanMode.BALANCED)
        self.assertFalse(widget.slider_cpu_fan.isEnabled())

        # Switch back to Auto
        widget.on_mode_selected(FanMode.AUTO)
        self.assertEqual(widget.fan_controller.current_mode, FanMode.AUTO)


class TestFanController(unittest.TestCase):
    def test_clamp_duty(self):
        """Test safety clamp bounds [25%, 100%]."""
        from alg_rgb_gui.fan_controller import clamp_duty
        self.assertEqual(clamp_duty(0), 25)
        self.assertEqual(clamp_duty(10), 25)
        self.assertEqual(clamp_duty(24), 25)
        self.assertEqual(clamp_duty(25), 25)
        self.assertEqual(clamp_duty(50), 50)
        self.assertEqual(clamp_duty(100), 100)
        self.assertEqual(clamp_duty(120), 100)

    def test_raw_conversions(self):
        """Test duty percentage <-> raw 8-bit conversions."""
        from alg_rgb_gui.fan_controller import pct_to_raw, raw_to_pct
        self.assertEqual(pct_to_raw(0), 0)
        self.assertEqual(pct_to_raw(50), 128)
        self.assertEqual(pct_to_raw(100), 255)
        self.assertEqual(raw_to_pct(0), 0)
        self.assertEqual(raw_to_pct(128), 50)
        self.assertEqual(raw_to_pct(255), 100)

    def test_curve_interpolation(self):
        """Test linear curve interpolation."""
        from alg_rgb_gui.fan_controller import interpolate_curve, BALANCED_CURVE
        # Below min threshold
        self.assertEqual(interpolate_curve(BALANCED_CURVE, 30.0), 30)
        # Exactly at first point (40C -> 30%)
        self.assertEqual(interpolate_curve(BALANCED_CURVE, 40.0), 30)
        # Midpoint between 40C (30%) and 50C (42%) -> ~36%
        self.assertEqual(interpolate_curve(BALANCED_CURVE, 45.0), 36)
        # Above max threshold (88C -> 100%)
        self.assertEqual(interpolate_curve(BALANCED_CURVE, 95.0), 100)

    def test_find_fan_cli_path(self):
        """Verify locating the alg-fan CLI binary."""
        from alg_rgb_gui.fan_controller import find_fan_cli_path
        cli = find_fan_cli_path()
        self.assertIsNotNone(cli, "alg-fan CLI should be located in cli/ or PATH")
        self.assertTrue(os.path.isfile(cli))
        self.assertTrue(os.access(cli, os.X_OK))

    def test_hardware_backend_safety_gate(self):
        """Verify hardware writes remain gated and log calls in simulation mode."""
        from alg_rgb_gui.fan_controller import FanHardwareBackend
        backend = FanHardwareBackend(hardware_writes_enabled=False)
        self.assertFalse(backend.hardware_writes_enabled)

        ok, msg = backend.apply_manual_duty(60, 70)
        self.assertTrue(ok)
        self.assertIn("Safety-Gated", msg)
        self.assertIn("SCMD 0x68", msg)
        self.assertEqual(backend.last_commanded_cpu_raw, 153)
        self.assertEqual(backend.last_commanded_gpu_raw, 178)
        self.assertEqual(len(backend.call_history), 1)

        ok, msg = backend.apply_auto_mode()
        self.assertTrue(ok)
        self.assertIn("Safety-Gated", msg)
        self.assertIn("SCMD 0x69", msg)
        self.assertEqual(len(backend.call_history), 2)

    def test_hardware_backend_device_file_io(self):
        """Verify real actuation writes formatted commands to device node."""
        from alg_rgb_gui.fan_controller import FanHardwareBackend
        import tempfile

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as tmp:
            backend = FanHardwareBackend(hardware_writes_enabled=True)
            backend.device_path = tmp.name

            # Test manual duty write
            ok, msg = backend.apply_manual_duty(50, 75)
            self.assertTrue(ok)
            self.assertIn("Hardware Applied", msg)
            tmp.seek(0)
            content = tmp.read()
            self.assertIn("50 75", content)

            # Test auto restore write
            ok, msg = backend.apply_auto_mode()
            self.assertTrue(ok)
            self.assertIn("Restored firmware automatic", msg)
            tmp.seek(0)
            content = tmp.read()
            self.assertIn("auto", content)

    def test_engine_independent_and_synced_duty(self):
        """Test engine independent CPU/GPU control and sync locking."""
        from alg_rgb_gui.fan_controller import FanControllerEngine, FanMode
        engine = FanControllerEngine()
        engine.set_mode(FanMode.CUSTOM)

        # Unsync fans
        engine.set_sync_fans(False)
        self.assertFalse(engine.sync_fans)

        # Set independent duties
        engine.set_custom_duty(1, 40)
        engine.set_custom_duty(2, 70)
        self.assertEqual(engine.custom_cpu_duty, 40)
        self.assertEqual(engine.custom_gpu_duty, 70)
        self.assertEqual(engine.active_cpu_target_pct, 40)
        self.assertEqual(engine.active_gpu_target_pct, 70)

        # Re-enable sync -> GPU duty snaps to CPU duty
        engine.set_sync_fans(True)
        self.assertEqual(engine.custom_gpu_duty, 40)
        self.assertEqual(engine.active_gpu_target_pct, 40)

        # In sync mode, changing Fan 1 updates Fan 2
        engine.set_custom_duty(1, 80)
        self.assertEqual(engine.custom_cpu_duty, 80)
        self.assertEqual(engine.custom_gpu_duty, 80)

    def test_emergency_thermal_override(self):
        """Test emergency 100% cooling trigger when temp >= 90C CPU or >= 85C GPU."""
        from alg_rgb_gui.fan_controller import FanControllerEngine, FanMode
        engine = FanControllerEngine()
        engine.set_mode(FanMode.SILENT)

        # Normal operation: 50C
        snapshot = engine.tick_thermal_update(50.0, 48.0)
        self.assertFalse(snapshot["emergency_override"])
        self.assertLess(snapshot["active_cpu_pct"], 100)

        # Critical CPU temp: 92C
        snapshot = engine.tick_thermal_update(92.0, 50.0)
        self.assertTrue(snapshot["emergency_override"])
        self.assertEqual(snapshot["active_cpu_pct"], 100)
        self.assertEqual(snapshot["active_gpu_pct"], 100)
        self.assertIn("EMERGENCY THERMAL SAFETY", snapshot["status_message"])

    def test_widget_instantiation(self):
        """Test ThermalsAndFanWidget GUI instantiation with all cards."""
        from PyQt6.QtWidgets import QApplication
        from alg_rgb_gui.fan_dashboard import ThermalsAndFanWidget
        app = QApplication.instance() or QApplication([])
        widget = ThermalsAndFanWidget()
        self.assertIsNotNone(widget.slider_cpu)
        self.assertIsNotNone(widget.slider_gpu)
        self.assertIsNotNone(widget.btn_auto)
        widget.update_telemetry()
        widget.stop_monitoring()


if __name__ == "__main__":
    unittest.main()
