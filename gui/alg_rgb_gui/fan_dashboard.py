"""
Thermal and Fan Control Dashboard for Acer ALG AL15G-52.
Displays real-time CPU core thermals, NVIDIA RTX 2050 telemetry,
storage temps, live 60-second rolling graph, and full Windows Control Center-style
fan controls (Auto, Silent, Balanced, Performance, Custom manual sliders).
"""

from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QProgressBar, QFrame, QPushButton, QScrollArea, QToolTip,
    QDialog, QTextBrowser, QDialogButtonBox, QSlider, QCheckBox
)
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from .sensors import SensorEngine, CpuTelemetry, GpuTelemetry, FanHardwareStatus
from .thermal_graph import TemperatureHistoryGraph
from .fan_controller import (
    FanMode, FanControllerEngine, FanHardwareBackend,
    clamp_duty, pct_to_raw, raw_to_pct
)
from .config import ConfigManager


class HardwareReportDialog(QDialog):
    """
    Detailed hardware architecture and thermal safety report modal
    for Acer ALG AL15G-52.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thermal Architecture & Hardware Safety Report")
        self.resize(700, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QTextBrowser {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 14px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(self._generate_report_markdown())
        layout.addWidget(browser)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @staticmethod
    def _generate_report_markdown() -> str:
        return (
            "# Acer ALG AL15G-52 Thermal Architecture & Safety Report\n\n"
            "## 1. System & Motherboard Identification\n"
            "- **Laptop Model:** Acer ALG AL15G-52\n"
            "- **Board Name:** Aspire Lite AL15G-52\n"
            "- **ACPI Hardware ID:** `CLV0001:00` (`\\_SB.DCHU`)\n"
            "- **Platform Architecture:** Clevo ODM white-label baseboard\n"
            "- **Hardware:** Intel Core i5-12450H (Alder Lake-P) + NVIDIA GeForce RTX 2050 Mobile\n\n"
            "## 2. Thermal Control & Cooling Architecture\n"
            "- **Dual Independent Cooling Fans:**\n"
            "  - **Fan 1 (CPU):** Dedicated heatpipe dissipation for the 8-core CPU package.\n"
            "  - **Fan 2 (GPU):** Dedicated heatpipe dissipation for the NVIDIA RTX 2050 GPU.\n"
            "- **Firmware Thermal Governor:**\n"
            "  - Cooling is managed by an autonomous on-board **Embedded Controller (EC)**.\n"
            "  - The EC continuously reads CPU DTS (via PECI bus) and GPU core thermals, comparing them "
            "against internal BIOS trip-point tables (`F1T1`..`F1T4`, `F2T1`..`F2T4`) to update duty cycles "
            "(`DUT1`, `DUT2`) directly in hardware.\n"
            "  - When thermals increase under load (gaming or compilation), fans automatically scale up; "
            "when idle, fans scale down to silent operation.\n\n"
            "## 3. Linux Kernel & Subsystem Status\n"
            "- **Standard `hwmon` PWM Interface:** Not Available\n"
            "  - Mainline Linux has no kernel driver for `CLV0001:00` thermal control.\n"
            "  - Standard Linux fan tools (`pwmconfig`, `lm-sensors`, `fancontrol`) require `/sys/class/hwmon/hwmon*/pwm*` "
            "channels, which are not registered by this chassis.\n"
            "  - Thermal cooling devices in `/sys/class/thermal/cooling_device*` only expose passive CPU throttling "
            "(`Processor`, `intel_powerclamp`, `TCC Offset`). No active fan cooling devices exist.\n\n"
            "## 4. ACPI Bytecode (DSDT) Audit Evidence\n"
            "- **Target Device:** `\\_SB.DCHU` (`CLV0001:00`)\n"
            "- **UUID:** `93f224e4-fbdc-4bbf-add6-db71bdc0afad`\n"
            "- **Function `0x67`:** Keyboard RGB Lighting (the only known, reverse-engineered, safe function implemented by `alg_rgb.ko`).\n"
            "- **Function `0x68` (`SCMD 0x68`):** Manual Fan Duty dispatch (`0xC1, fan_id, duty`).\n"
            "- **Function `0x69` (`SCMD 0x69`):** Auto Fan Restore dispatch (`0xC1, 0xFF, fan_id`).\n"
            "- **Function `0x0C` (`PK0C`):** Reads fan tachometer period registers (`RPM1`, `RPM2`) alongside battery registers.\n"
            "- **Function `0x0D` / `0x0E` (`PK0D` / `PK0E`):** Reads/writes BIOS fan trip points (`F1T1..F1T4`, `F1D1..F1D4`).\n\n"
            "## 5. Why Direct EC Writing is Strictly Prevented\n"
            "- Community workarounds (e.g. `ec_sys write_support=1`) attempt to force manual PWM by writing directly to EC registers.\n"
            "- Linux kernel maintainers explicitly document `ec_sys write_support` as: "
            "`\"Dangerous, reboot and removal of battery may be needed.\"*`\n"
            "- On Clevo ECs, blind register writes cause bus collisions, battery desync, system hard-lockups, "
            "or dangerous thermal runaway if userspace freezes while fans are manually throttled.\n"
            "- **Safety Guarantee:** Preserving the firmware's closed-loop automatic management ensures the laptop will never overheat, "
            "protecting the hardware from thermal damage."
        )


class ThermalsAndFanWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sensor_engine = SensorEngine()
        self.config_mgr = ConfigManager()
        self.fan_engine = FanControllerEngine()

        # Load persisted fan settings
        saved_mode_str = self.config_mgr.get("fan_mode", "auto")
        try:
            self.fan_engine.set_mode(FanMode(saved_mode_str))
        except Exception:
            self.fan_engine.set_mode(FanMode.AUTO)

        self.fan_engine.custom_cpu_duty = int(self.config_mgr.get("custom_cpu_duty", 50))
        self.fan_engine.custom_gpu_duty = int(self.config_mgr.get("custom_gpu_duty", 50))
        self.fan_engine.sync_fans = bool(self.config_mgr.get("sync_fans", True))

        self.init_ui()
        self.update_mode_ui_state()

        # Live telemetry polling timer (1 second interval)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self.update_telemetry)
        self.poll_timer.start()

        # Immediate first read
        self.update_telemetry()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(14)

        # =====================================================================
        # 1. FAN MODE SELECTION CARD (Windows-Style Profile Selector)
        # =====================================================================
        mode_card = QFrame()
        mode_card.setProperty("class", "cardFrame")
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(14, 14, 14, 14)
        mode_layout.setSpacing(10)

        mode_header = QHBoxLayout()
        m_title = QLabel("Fan & Cooling Mode")
        m_title.setProperty("class", "sectionTitle")
        mode_header.addWidget(m_title)
        mode_header.addStretch()

        self.lbl_mode_badge = QLabel("FIRMWARE AUTOMATIC")
        self.lbl_mode_badge.setStyleSheet(
            "background-color: #1e3a2f; color: #a6e3a1; "
            "border: 1px solid #10b981; border-radius: 6px; "
            "padding: 3px 10px; font-size: 11px; font-weight: bold;"
        )
        mode_header.addWidget(self.lbl_mode_badge)
        mode_layout.addLayout(mode_header)

        # Mode Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_auto = QPushButton("🛡️ Auto (Firmware)")
        self.btn_silent = QPushButton("🌙 Silent")
        self.btn_balanced = QPushButton("⚖️ Balanced")
        self.btn_perf = QPushButton("⚡ Performance")
        self.btn_custom = QPushButton("🎛️ Custom (Sliders)")

        self.mode_buttons = {
            FanMode.AUTO: self.btn_auto,
            FanMode.SILENT: self.btn_silent,
            FanMode.BALANCED: self.btn_balanced,
            FanMode.PERFORMANCE: self.btn_perf,
            FanMode.CUSTOM: self.btn_custom,
        }

        for mode, btn in self.mode_buttons.items():
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _, m=mode: self.on_mode_button_clicked(m))
            btn_row.addWidget(btn)

        mode_layout.addLayout(btn_row)
        main_layout.addWidget(mode_card)

        # =====================================================================
        # 2. ACTUATION & CUSTOM CONTROLS CARD
        # =====================================================================
        act_card = QFrame()
        act_card.setProperty("class", "cardFrame")
        act_layout = QVBoxLayout(act_card)
        act_layout.setContentsMargins(14, 14, 14, 14)
        act_layout.setSpacing(12)

        act_header = QHBoxLayout()
        act_title = QLabel("Fan Speed Actuation & Custom Targets")
        act_title.setProperty("class", "sectionTitle")
        act_header.addWidget(act_title)
        act_header.addStretch()

        self.lbl_safety_gate = QLabel("🔒 Phase 2 Safety Gate: Hardware Writes Gated")
        self.lbl_safety_gate.setStyleSheet(
            "background-color: #2e261e; color: #fab387; "
            "border: 1px solid #f59e0b; border-radius: 6px; "
            "padding: 3px 10px; font-size: 10px; font-weight: bold;"
        )
        act_header.addWidget(self.lbl_safety_gate)
        act_layout.addLayout(act_header)

        # CPU Fan Slider Row
        cpu_slider_row = QHBoxLayout()
        lbl_cpu_fan = QLabel("CPU Fan 1 Target:")
        lbl_cpu_fan.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 12px; min-width: 130px;")
        cpu_slider_row.addWidget(lbl_cpu_fan)

        self.slider_cpu = QSlider(Qt.Orientation.Horizontal)
        self.slider_cpu.setRange(25, 100)
        self.slider_cpu.setValue(self.fan_engine.custom_cpu_duty)
        self.slider_cpu.valueChanged.connect(self.on_cpu_slider_changed)
        cpu_slider_row.addWidget(self.slider_cpu)

        self.lbl_cpu_val = QLabel(f"{self.fan_engine.custom_cpu_duty}% (Raw: {pct_to_raw(self.fan_engine.custom_cpu_duty)}/255)")
        self.lbl_cpu_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #cdd6f4; min-width: 140px;")
        cpu_slider_row.addWidget(self.lbl_cpu_val)
        act_layout.addLayout(cpu_slider_row)

        # GPU Fan Slider Row
        gpu_slider_row = QHBoxLayout()
        lbl_gpu_fan = QLabel("GPU Fan 2 Target:")
        lbl_gpu_fan.setStyleSheet("font-weight: 600; color: #a6e3a1; font-size: 12px; min-width: 130px;")
        gpu_slider_row.addWidget(lbl_gpu_fan)

        self.slider_gpu = QSlider(Qt.Orientation.Horizontal)
        self.slider_gpu.setRange(25, 100)
        self.slider_gpu.setValue(self.fan_engine.custom_gpu_duty)
        self.slider_gpu.valueChanged.connect(self.on_gpu_slider_changed)
        gpu_slider_row.addWidget(self.slider_gpu)

        self.lbl_gpu_val = QLabel(f"{self.fan_engine.custom_gpu_duty}% (Raw: {pct_to_raw(self.fan_engine.custom_gpu_duty)}/255)")
        self.lbl_gpu_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #cdd6f4; min-width: 140px;")
        gpu_slider_row.addWidget(self.lbl_gpu_val)
        act_layout.addLayout(gpu_slider_row)

        # Bottom Controls: Link Fans & Quick Presets
        controls_row = QHBoxLayout()
        controls_row.setSpacing(10)

        self.chk_sync = QCheckBox("🔗 Link CPU & GPU Fan Speeds")
        self.chk_sync.setChecked(self.fan_engine.sync_fans)
        self.chk_sync.toggled.connect(self.on_sync_toggled)
        self.chk_sync.setStyleSheet("color: #cdd6f4; font-size: 11px; font-weight: 500;")
        controls_row.addWidget(self.chk_sync)

        controls_row.addStretch()

        preset_lbl = QLabel("Quick Presets:")
        preset_lbl.setStyleSheet("color: #6c7086; font-size: 10px;")
        controls_row.addWidget(preset_lbl)

        for p_val in (25, 50, 75, 100):
            p_btn = QPushButton(f"{p_val}%" if p_val not in (25, 100) else (f"Min ({p_val}%)" if p_val == 25 else f"Max ({p_val}%)"))
            p_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            p_btn.setStyleSheet(
                "QPushButton { background: #181825; border: 1px solid #313244; "
                "border-radius: 4px; padding: 3px 8px; font-size: 10px; color: #a6adc8; }"
                "QPushButton:hover { background: #26273a; border-color: #89b4fa; color: #cdd6f4; }"
            )
            p_btn.clicked.connect(lambda _, v=p_val: self.on_quick_preset_clicked(v))
            controls_row.addWidget(p_btn)

        act_layout.addLayout(controls_row)

        # Status text strip
        status_box = QFrame()
        status_box.setStyleSheet(
            "background-color: #181825; border: 1px solid #313244; "
            "border-radius: 6px; padding: 8px 12px;"
        )
        sb_layout = QHBoxLayout(status_box)
        sb_layout.setContentsMargins(4, 4, 4, 4)
        sb_layout.setSpacing(10)

        self.lbl_fan_status_detail = QLabel("Status: Firmware Automatic (EC Closed-Loop Active)")
        self.lbl_fan_status_detail.setStyleSheet("font-size: 11px; color: #cdd6f4; font-weight: 500;")
        sb_layout.addWidget(self.lbl_fan_status_detail)
        sb_layout.addStretch()

        btn_report = QPushButton("Hardware Architecture & Safety Report")
        btn_report.setIcon(QIcon.fromTheme("help-about"))
        btn_report.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_report.setStyleSheet(
            "QPushButton {"
            "    background-color: #1e1e2e; color: #89b4fa; border: 1px solid #313244;"
            "    border-radius: 4px; padding: 4px 10px; font-size: 10px; font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "    background-color: #26273a; border-color: #89b4fa;"
            "}"
        )
        btn_report.clicked.connect(self.show_hardware_report)
        sb_layout.addWidget(btn_report)

        act_layout.addWidget(status_box)
        main_layout.addWidget(act_card)

        # =====================================================================
        # 3. LIVE TEMPERATURE HISTORY GRAPH CARD
        # =====================================================================
        graph_card = QFrame()
        graph_card.setProperty("class", "cardFrame")
        graph_layout = QVBoxLayout(graph_card)
        graph_layout.setContentsMargins(12, 12, 12, 12)
        graph_layout.setSpacing(8)

        g_header = QHBoxLayout()
        g_title = QLabel("Live Thermal History (Last 60 Seconds)")
        g_title.setProperty("class", "sectionTitle")
        g_header.addWidget(g_title)
        g_header.addStretch()

        self.lbl_poll_status = QLabel("Polling: 1.0s")
        self.lbl_poll_status.setStyleSheet("font-size: 10px; color: #6c7086;")
        g_header.addWidget(self.lbl_poll_status)
        graph_layout.addLayout(g_header)

        self.graph_widget = TemperatureHistoryGraph(self)
        graph_layout.addWidget(self.graph_widget)
        main_layout.addWidget(graph_card)

        # =====================================================================
        # 4. DUAL PROCESSOR TELEMETRY: CPU & GPU
        # =====================================================================
        proc_row = QHBoxLayout()
        proc_row.setSpacing(14)

        # CPU Card
        self.cpu_card = QFrame()
        self.cpu_card.setProperty("class", "cardFrame")
        cpu_layout = QVBoxLayout(self.cpu_card)
        cpu_layout.setContentsMargins(12, 12, 12, 12)
        cpu_layout.setSpacing(8)

        cpu_title_row = QHBoxLayout()
        cpu_title = QLabel("Intel Core (Alder Lake-P)")
        cpu_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 13px;")
        cpu_title_row.addWidget(cpu_title)
        cpu_title_row.addStretch()
        self.lbl_cpu_pkg = QLabel("--°C")
        self.lbl_cpu_pkg.setStyleSheet("font-size: 18px; font-weight: bold; color: #cdd6f4;")
        cpu_title_row.addWidget(self.lbl_cpu_pkg)
        cpu_layout.addLayout(cpu_title_row)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(20, 100)
        self.cpu_bar.setValue(50)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setFixedHeight(8)
        self.cpu_bar.setStyleSheet(
            "QProgressBar { background: #181926; border-radius: 4px; }"
            "QProgressBar::chunk { background: #38bdf8; border-radius: 4px; }"
        )
        cpu_layout.addWidget(self.cpu_bar)

        self.lbl_cpu_stats = QLabel("Max Core: --°C | Avg: --°C")
        self.lbl_cpu_stats.setStyleSheet("font-size: 11px; color: #a6adc8;")
        cpu_layout.addWidget(self.lbl_cpu_stats)

        # Core breakdown grid
        self.core_labels = {}
        core_grid = QGridLayout()
        core_grid.setSpacing(4)
        for i in range(8):
            core_lbl = QLabel(f"Core {i}: --°C")
            core_lbl.setStyleSheet("font-size: 10px; color: #6c7086;")
            core_grid.addWidget(core_lbl, i // 4, i % 4)
            self.core_labels[i] = core_lbl
        cpu_layout.addLayout(core_grid)

        self.lbl_cpu_fan_status = QLabel("Cooling: Fan 1 (EC Closed-Loop Active)")
        self.lbl_cpu_fan_status.setStyleSheet("font-size: 10px; color: #89b4fa; font-weight: 500;")
        cpu_layout.addWidget(self.lbl_cpu_fan_status)

        proc_row.addWidget(self.cpu_card)

        # GPU Card
        self.gpu_card = QFrame()
        self.gpu_card.setProperty("class", "cardFrame")
        gpu_layout = QVBoxLayout(self.gpu_card)
        gpu_layout.setContentsMargins(12, 12, 12, 12)
        gpu_layout.setSpacing(8)

        gpu_title_row = QHBoxLayout()
        gpu_title = QLabel("NVIDIA GeForce RTX 2050")
        gpu_title.setStyleSheet("font-weight: bold; color: #a6e3a1; font-size: 13px;")
        gpu_title_row.addWidget(gpu_title)
        gpu_title_row.addStretch()
        self.lbl_gpu_temp = QLabel("--°C")
        self.lbl_gpu_temp.setStyleSheet("font-size: 18px; font-weight: bold; color: #cdd6f4;")
        gpu_title_row.addWidget(self.lbl_gpu_temp)
        gpu_layout.addLayout(gpu_title_row)

        self.gpu_bar = QProgressBar()
        self.gpu_bar.setRange(20, 100)
        self.gpu_bar.setValue(45)
        self.gpu_bar.setTextVisible(False)
        self.gpu_bar.setFixedHeight(8)
        self.gpu_bar.setStyleSheet(
            "QProgressBar { background: #181926; border-radius: 4px; }"
            "QProgressBar::chunk { background: #a6e3a1; border-radius: 4px; }"
        )
        gpu_layout.addWidget(self.gpu_bar)

        self.lbl_gpu_load = QLabel("Load: --% | Power: -- W")
        self.lbl_gpu_load.setStyleSheet("font-size: 11px; color: #a6adc8;")
        gpu_layout.addWidget(self.lbl_gpu_load)

        self.lbl_gpu_vram = QLabel("VRAM: -- MB / -- MB")
        self.lbl_gpu_vram.setStyleSheet("font-size: 11px; color: #a6adc8;")
        gpu_layout.addWidget(self.lbl_gpu_vram)

        self.lbl_gpu_driver = QLabel("Driver: NVIDIA 615.78")
        self.lbl_gpu_driver.setStyleSheet("font-size: 10px; color: #6c7086;")
        gpu_layout.addWidget(self.lbl_gpu_driver)

        self.lbl_gpu_fan_status = QLabel("Cooling: Fan 2 (EC Closed-Loop Active)")
        self.lbl_gpu_fan_status.setStyleSheet("font-size: 10px; color: #89b4fa; font-weight: 500;")
        gpu_layout.addWidget(self.lbl_gpu_fan_status)

        proc_row.addWidget(self.gpu_card)
        main_layout.addLayout(proc_row)

        # =====================================================================
        # 5. AUXILIARY SYSTEM THERMALS CARD
        # =====================================================================
        aux_card = QFrame()
        aux_card.setProperty("class", "cardFrame")
        aux_layout = QVBoxLayout(aux_card)
        aux_layout.setContentsMargins(12, 12, 12, 12)
        aux_layout.setSpacing(8)

        aux_title = QLabel("System & Storage Temperatures")
        aux_title.setProperty("class", "sectionTitle")
        aux_layout.addWidget(aux_title)

        self.aux_grid = QGridLayout()
        self.aux_grid.setSpacing(10)

        self.aux_nvme_lbl = QLabel("NVMe SSD: --°C")
        self.aux_acpi_lbl = QLabel("ACPI Thermal Zone: --°C")
        self.aux_wifi_lbl = QLabel("Wi-Fi Adapter: --°C")

        for lbl in (self.aux_nvme_lbl, self.aux_acpi_lbl, self.aux_wifi_lbl):
            lbl.setStyleSheet(
                "background-color: #181825; border: 1px solid #313244; "
                "border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 500;"
            )

        self.aux_grid.addWidget(self.aux_nvme_lbl, 0, 0)
        self.aux_grid.addWidget(self.aux_acpi_lbl, 0, 1)
        self.aux_grid.addWidget(self.aux_wifi_lbl, 0, 2)
        aux_layout.addLayout(self.aux_grid)

        main_layout.addWidget(aux_card)

    def on_mode_button_clicked(self, mode: FanMode):
        self.fan_engine.set_mode(mode)
        self.config_mgr.set("fan_mode", mode.value)
        self.update_mode_ui_state()
        self.refresh_status_labels()

    def update_mode_ui_state(self):
        current = self.fan_engine.current_mode

        # Define button themes
        btn_styles = {
            FanMode.AUTO: ("#1e3a2f", "#10b981", "#a6e3a1"),
            FanMode.SILENT: ("#1e2a3a", "#38bdf8", "#7dd3fc"),
            FanMode.BALANCED: ("#252538", "#89b4fa", "#cdd6f4"),
            FanMode.PERFORMANCE: ("#3a2025", "#f38ba8", "#f5c2e7"),
            FanMode.CUSTOM: ("#2e1e3a", "#cba6f7", "#f5c2e7"),
        }

        for mode, btn in self.mode_buttons.items():
            if mode == current:
                bg, border, col = btn_styles[mode]
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {bg}; border: 1px solid {border}; "
                    f"border-radius: 6px; color: {col}; font-weight: bold; font-size: 11px; }}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color: #181825; border: 1px solid #313244; "
                    "border-radius: 6px; color: #a6adc8; font-weight: 500; font-size: 11px; }"
                    "QPushButton:hover { background-color: #26273a; border-color: #45475a; color: #cdd6f4; }"
                )

        badge_texts = {
            FanMode.AUTO: ("FIRMWARE AUTOMATIC", "#1e3a2f", "#10b981", "#a6e3a1"),
            FanMode.SILENT: ("SILENT PROFILE", "#1e2a3a", "#38bdf8", "#7dd3fc"),
            FanMode.BALANCED: ("BALANCED PROFILE", "#252538", "#89b4fa", "#cdd6f4"),
            FanMode.PERFORMANCE: ("PERFORMANCE PROFILE", "#3a2025", "#f38ba8", "#f5c2e7"),
            FanMode.CUSTOM: ("CUSTOM MANUAL", "#2e1e3a", "#cba6f7", "#f5c2e7"),
        }

        b_text, b_bg, b_border, b_col = badge_texts[current]
        self.lbl_mode_badge.setText(b_text)
        self.lbl_mode_badge.setStyleSheet(
            f"background-color: {b_bg}; color: {b_col}; "
            f"border: 1px solid {b_border}; border-radius: 6px; "
            f"padding: 3px 10px; font-size: 11px; font-weight: bold;"
        )

        is_custom = (current == FanMode.CUSTOM)
        self.slider_cpu.setEnabled(is_custom)
        self.slider_gpu.setEnabled(is_custom)
        self.chk_sync.setEnabled(is_custom)

        if is_custom:
            self.slider_cpu.setValue(self.fan_engine.custom_cpu_duty)
            self.slider_gpu.setValue(self.fan_engine.custom_gpu_duty)
            self.lbl_cpu_val.setText(f"{self.fan_engine.custom_cpu_duty}% (Raw: {pct_to_raw(self.fan_engine.custom_cpu_duty)}/255)")
            self.lbl_gpu_val.setText(f"{self.fan_engine.custom_gpu_duty}% (Raw: {pct_to_raw(self.fan_engine.custom_gpu_duty)}/255)")

    def on_cpu_slider_changed(self, value: int):
        self.lbl_cpu_val.setText(f"{value}% (Raw: {pct_to_raw(value)}/255)")
        if self.fan_engine.sync_fans:
            self.slider_gpu.blockSignals(True)
            self.slider_gpu.setValue(value)
            self.lbl_gpu_val.setText(f"{value}% (Raw: {pct_to_raw(value)}/255)")
            self.slider_gpu.blockSignals(False)
            self.fan_engine.set_custom_duty(2, value)

        self.fan_engine.set_custom_duty(1, value)
        self.config_mgr.set("custom_cpu_duty", value)
        if self.fan_engine.sync_fans:
            self.config_mgr.set("custom_gpu_duty", value)
        self.refresh_status_labels()

    def on_gpu_slider_changed(self, value: int):
        self.lbl_gpu_val.setText(f"{value}% (Raw: {pct_to_raw(value)}/255)")
        if self.fan_engine.sync_fans:
            self.slider_cpu.blockSignals(True)
            self.slider_cpu.setValue(value)
            self.lbl_cpu_val.setText(f"{value}% (Raw: {pct_to_raw(value)}/255)")
            self.slider_cpu.blockSignals(False)
            self.fan_engine.set_custom_duty(1, value)

        self.fan_engine.set_custom_duty(2, value)
        self.config_mgr.set("custom_gpu_duty", value)
        if self.fan_engine.sync_fans:
            self.config_mgr.set("custom_cpu_duty", value)
        self.refresh_status_labels()

    def on_sync_toggled(self, checked: bool):
        self.fan_engine.sync_fans = checked
        self.config_mgr.set("sync_fans", checked)
        if checked:
            self.on_cpu_slider_changed(self.slider_cpu.value())

    def on_quick_preset_clicked(self, val: int):
        if self.fan_engine.current_mode != FanMode.CUSTOM:
            self.on_mode_button_clicked(FanMode.CUSTOM)
        self.slider_cpu.setValue(val)
        if not self.fan_engine.sync_fans:
            self.slider_gpu.setValue(val)

    def refresh_status_labels(self):
        state = self.fan_engine.get_state_snapshot()
        mode_val = state["mode"].upper()

        if state["mode"] == "auto":
            self.lbl_fan_status_detail.setText("Status: Firmware Automatic (Autonomous Closed-Loop EC Table Active)")
            self.lbl_cpu_fan_status.setText("Cooling: Fan 1 (EC Firmware Auto)")
            self.lbl_gpu_fan_status.setText("Cooling: Fan 2 (EC Firmware Auto)")
        elif state["mode"] == "custom":
            self.lbl_fan_status_detail.setText(
                f"Target: CPU Fan 1 = {state['custom_cpu_duty']}% ({pct_to_raw(state['custom_cpu_duty'])}/255) | "
                f"GPU Fan 2 = {state['custom_gpu_duty']}% ({pct_to_raw(state['custom_gpu_duty'])}/255) [Manual Sliders]"
            )
            self.lbl_cpu_fan_status.setText(f"Cooling: Fan 1 Target = {state['custom_cpu_duty']}%")
            self.lbl_gpu_fan_status.setText(f"Cooling: Fan 2 Target = {state['custom_gpu_duty']}%")
        else:
            self.lbl_fan_status_detail.setText(
                f"Profile [{mode_val}]: Active Target = {state['active_cpu_pct']}% ({state['active_cpu_raw']}/255) "
                f"[Dynamic Thermal Curve]"
            )
            self.lbl_cpu_fan_status.setText(f"Cooling: Fan 1 Target = {state['active_cpu_pct']}% (Curve)")
            self.lbl_gpu_fan_status.setText(f"Cooling: Fan 2 Target = {state['active_gpu_pct']}% (Curve)")

        if state["emergency_override"]:
            self.lbl_fan_status_detail.setText(f"⚠️ {state['status_message']}")

    def update_telemetry(self):
        # 1. CPU Telemetry
        cpu = self.sensor_engine.read_cpu_telemetry()
        if cpu.sensor_found:
            self.lbl_cpu_pkg.setText(f"{cpu.package_temp:.0f}°C")
            self.cpu_bar.setValue(int(cpu.package_temp))

            if cpu.package_temp >= 85:
                bar_color = "#f38ba8"
            elif cpu.package_temp >= 70:
                bar_color = "#fab387"
            else:
                bar_color = "#38bdf8"

            self.cpu_bar.setStyleSheet(
                "QProgressBar { background: #181926; border-radius: 4px; }"
                f"QProgressBar::chunk {{ background: {bar_color}; border-radius: 4px; }}"
            )

            self.lbl_cpu_stats.setText(f"Max Core: {cpu.max_core_temp:.0f}°C | Avg: {cpu.avg_core_temp:.0f}°C")

            for idx, c in enumerate(cpu.cores[:8]):
                if idx in self.core_labels:
                    self.core_labels[idx].setText(f"{c.label}: {c.temp_c:.0f}°C")

        # 2. GPU Telemetry
        gpu = self.sensor_engine.read_gpu_telemetry()
        if gpu.available:
            self.lbl_gpu_temp.setText(f"{gpu.temp_c:.0f}°C")
            self.gpu_bar.setValue(int(gpu.temp_c))
            self.lbl_gpu_load.setText(f"Load: {gpu.utilization_pct}% | Power: {gpu.power_draw_w:.1f} W")
            self.lbl_gpu_vram.setText(f"VRAM: {gpu.vram_used_mb} MB / {gpu.vram_total_mb} MB")
            if gpu.driver_version:
                self.lbl_gpu_driver.setText(f"Driver: NVIDIA {gpu.driver_version}")
        else:
            self.lbl_gpu_temp.setText("Standby")
            self.gpu_bar.setValue(20)
            self.lbl_gpu_load.setText("NVIDIA GPU in low-power standby")

        # 3. Fan Controller Thermal Tick
        cpu_temp = cpu.package_temp if cpu.sensor_found and cpu.package_temp > 0 else 45.0
        gpu_temp = gpu.temp_c if gpu.available else 40.0
        snapshot = self.fan_engine.tick_thermal_update(cpu_temp, gpu_temp)

        # Reflect dynamic target on sliders when in curve mode
        if self.fan_engine.current_mode in (FanMode.SILENT, FanMode.BALANCED, FanMode.PERFORMANCE):
            target = snapshot["active_cpu_pct"]
            self.slider_cpu.blockSignals(True)
            self.slider_gpu.blockSignals(True)
            self.slider_cpu.setValue(target)
            self.slider_gpu.setValue(target)
            self.lbl_cpu_val.setText(f"{target}% (Curve Target)")
            self.lbl_gpu_val.setText(f"{target}% (Curve Target)")
            self.slider_cpu.blockSignals(False)
            self.slider_gpu.blockSignals(False)

        self.refresh_status_labels()

        # 4. Add to live graph
        self.graph_widget.add_sample(
            cpu.package_temp if cpu.package_temp > 0 else 45.0,
            gpu.temp_c if gpu.available else 0.0
        )

        # 5. Auxiliary System Temps
        aux = self.sensor_engine.read_auxiliary_temperatures()
        if "NVMe SSD" in aux:
            self.aux_nvme_lbl.setText(f"💾 NVMe SSD: {aux['NVMe SSD']:.1f}°C")
        if "ACPI Motherboard" in aux:
            self.aux_acpi_lbl.setText(f"🌡️ ACPI Board: {aux['ACPI Motherboard']:.0f}°C")
        if "Wi-Fi Module" in aux:
            self.aux_wifi_lbl.setText(f"📶 Wi-Fi: {aux['Wi-Fi Module']:.0f}°C")

    def stop_monitoring(self):
        self.poll_timer.stop()

    def show_hardware_report(self):
        dlg = HardwareReportDialog(self)
        dlg.exec()
