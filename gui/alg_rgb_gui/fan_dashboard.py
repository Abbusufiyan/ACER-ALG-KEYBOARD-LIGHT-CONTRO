"""
Thermal and Fan Control Dashboard for Acer ALG AL15G-52.
Displays real-time CPU core thermals, NVIDIA RTX 2050 telemetry,
storage temps, live 60-second rolling graph, and firmware cooling status.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QProgressBar, QFrame, QPushButton, QScrollArea, QToolTip
)
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from .sensors import SensorEngine, CpuTelemetry, GpuTelemetry, FanHardwareStatus
from .thermal_graph import TemperatureHistoryGraph


class ThermalsAndFanWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sensor_engine = SensorEngine()

        self.init_ui()

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

        # --- 1. FAN MODE & HARDWARE STATUS CARD ---
        mode_card = QFrame()
        mode_card.setProperty("class", "cardFrame")
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(12, 12, 12, 12)
        mode_layout.setSpacing(10)

        mode_header = QHBoxLayout()
        m_title = QLabel("Fan & Thermal Control Mode")
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

        # Info & Hardware Explanation Strip
        exp_box = QFrame()
        exp_box.setStyleSheet(
            "background-color: #181825; border: 1px solid #313244; "
            "border-radius: 8px; padding: 10px;"
        )
        exp_layout = QHBoxLayout(exp_box)
        exp_layout.setContentsMargins(8, 8, 8, 8)
        exp_layout.setSpacing(12)

        shield_lbl = QLabel("🛡️")
        shield_lbl.setStyleSheet("font-size: 22px;")
        exp_layout.addWidget(shield_lbl)

        exp_vbox = QVBoxLayout()
        exp_vbox.setSpacing(2)
        exp_title = QLabel("Embedded Controller Protection Active")
        exp_title.setStyleSheet("font-weight: bold; color: #cdd6f4; font-size: 12px;")
        exp_desc = QLabel(
            "The Acer ALG AL15G-52 hardware controller autonomously regulates fan speeds "
            "using BIOS thermal tables. Standard Linux drivers do not expose a PWM override knob; "
            "firmware protection prevents thermal runaway or accidental fan stoppage."
        )
        exp_desc.setWordWrap(True)
        exp_desc.setStyleSheet("font-size: 11px; color: #a6adc8;")
        exp_vbox.addWidget(exp_title)
        exp_vbox.addWidget(exp_desc)
        exp_layout.addLayout(exp_vbox)

        mode_layout.addWidget(exp_box)
        main_layout.addWidget(mode_card)

        # --- 2. LIVE TEMPERATURE HISTORY GRAPH CARD ---
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

        # --- 3. DUAL PROCESSOR TELEMETRY: CPU & GPU ---
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

        proc_row.addWidget(self.gpu_card)
        main_layout.addLayout(proc_row)

        # --- 4. AUXILIARY SYSTEM THERMALS CARD ---
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

        # Placeholders for NVMe, ACPI, Wi-Fi
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

    def update_telemetry(self):
        # 1. CPU Telemetry
        cpu = self.sensor_engine.read_cpu_telemetry()
        if cpu.sensor_found:
            self.lbl_cpu_pkg.setText(f"{cpu.package_temp:.0f}°C")
            self.cpu_bar.setValue(int(cpu.package_temp))

            # Dynamic bar color based on temp
            if cpu.package_temp >= 85:
                bar_color = "#f38ba8"  # Hot Red
            elif cpu.package_temp >= 70:
                bar_color = "#fab387"  # Warm Amber
            else:
                bar_color = "#38bdf8"  # Normal Blue

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

        # 3. Add to live graph
        self.graph_widget.add_sample(
            cpu.package_temp if cpu.package_temp > 0 else 45.0,
            gpu.temp_c if gpu.available else 0.0
        )

        # 4. Auxiliary System Temps
        aux = self.sensor_engine.read_auxiliary_temperatures()
        if "NVMe SSD" in aux:
            self.aux_nvme_lbl.setText(f"💾 NVMe SSD: {aux['NVMe SSD']:.1f}°C")
        if "ACPI Motherboard" in aux:
            self.aux_acpi_lbl.setText(f"🌡️ ACPI Board: {aux['ACPI Motherboard']:.0f}°C")
        if "Wi-Fi Module" in aux:
            self.aux_wifi_lbl.setText(f"📶 Wi-Fi: {aux['Wi-Fi Module']:.0f}°C")

    def stop_monitoring(self):
        self.poll_timer.stop()
