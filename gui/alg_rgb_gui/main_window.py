"""
Primary Main Window for Acer ALG RGB GUI.
Combines keyboard preview, color palette, custom hex picker, brightness slider,
system diagnostics, and autostart preferences.
"""

import os
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QTabWidget, QLineEdit, QCheckBox,
    QColorDialog, QScrollArea, QFrame, QMessageBox, QButtonGroup,
    QGraphicsDropShadowEffect, QApplication
)
from PyQt6.QtGui import QIcon, QColor, QFont, QPixmap, QPainter
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from .colors import (
    AlgColor, SUPPORTED_COLORS, COLOR_OFF,
    get_color, hex_to_rgb, rgb_to_hex, find_nearest_preset
)
from .backend import apply_color, turn_off, read_diagnostics, find_cli_path
from .config import ConfigManager
from .preview import KeyboardPreviewWidget
from .tray import AlgTrayIcon


class ColorSwatchButton(QPushButton):
    """Circular/Pill color swatch button representing a firmware color preset."""
    def __init__(self, color_item: AlgColor, parent=None):
        super().__init__(parent)
        self.color_item = color_item
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setToolTip(f"{color_item.label} ({color_item.hex_code})")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Color dot indicator
        self.dot = QLabel()
        self.dot.setFixedSize(22, 22)
        self.dot.setStyleSheet(
            f"background-color: {color_item.hex_code}; "
            f"border: 1px solid #ffffff40; "
            f"border-radius: 11px;"
        )
        layout.addWidget(self.dot)

        # Text labels
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)
        name_lbl = QLabel(color_item.label)
        name_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #cdd6f4;")
        hex_lbl = QLabel(color_item.hex_code)
        hex_lbl.setStyleSheet("font-size: 10px; color: #a6adc8;")
        info_layout.addWidget(name_lbl)
        info_layout.addWidget(hex_lbl)
        layout.addLayout(info_layout)
        layout.addStretch()

        self.update_selection_style(False)

    def update_selection_style(self, selected: bool):
        self.setChecked(selected)
        if selected:
            self.setStyleSheet(
                "QPushButton {"
                "  background-color: #27293d;"
                "  border: 2px solid #38bdf8;"
                "  border-radius: 8px;"
                "}"
            )
        else:
            self.setStyleSheet(
                "QPushButton {"
                "  background-color: #1e1e2e;"
                "  border: 1px solid #313244;"
                "  border-radius: 8px;"
                "}"
                "QPushButton:hover {"
                "  background-color: #24273a;"
                "  border-color: #45475a;"
                "}"
            )


class AcerAlgRgbWindow(QMainWindow):
    def __init__(self, icon_path: str):
        super().__init__()
        self.icon_path = icon_path
        self.config = ConfigManager()

        # State tracking
        self.current_color: AlgColor = SUPPORTED_COLORS[0]
        self.current_brightness: int = 4
        self.power_on: bool = True
        self.is_applied: bool = True

        # Debounce timer for slider / color changes
        self.apply_timer = QTimer(self)
        self.apply_timer.setSingleShot(True)
        self.apply_timer.setInterval(160)
        self.apply_timer.timeout.connect(self._on_debounced_apply)

        # Periodic status refresh timer (every 4 seconds)
        self.diag_timer = QTimer(self)
        self.diag_timer.setInterval(4000)
        self.diag_timer.timeout.connect(self.refresh_diagnostics)

        # Initialize UI & Tray
        self.init_ui()
        self.init_tray()

        # Restore saved config or detect current driver state
        self.restore_initial_state()
        self.diag_timer.start()

    def init_ui(self):
        self.setWindowTitle("Acer ALG RGB - Keyboard Lighting")
        self.resize(640, 780)
        self.setMinimumSize(560, 680)
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))

        # Main scrollable container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # --- 1. HEADER BAR ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_lbl = QLabel("Acer ALG RGB")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f5e0dc;")
        title_row.addWidget(title_lbl)

        model_badge = QLabel("AL15G-52")
        model_badge.setStyleSheet(
            "background-color: #1e2030; color: #89dceb; "
            "border: 1px solid #38bdf8; border-radius: 6px; "
            "padding: 2px 7px; font-size: 11px; font-weight: bold;"
        )
        title_row.addWidget(model_badge)
        title_row.addStretch()

        sub_lbl = QLabel("Built-in Keyboard RGB Lighting Controller")
        sub_lbl.setStyleSheet("font-size: 11px; color: #a6adc8;")

        title_vbox.addLayout(title_row)
        title_vbox.addWidget(sub_lbl)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        # Quick Power Switch in header
        self.btn_power_toggle = QPushButton("Turn Off")
        self.btn_power_toggle.setProperty("class", "offButton")
        self.btn_power_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_power_toggle.clicked.connect(self.toggle_power)
        header_layout.addWidget(self.btn_power_toggle)

        main_layout.addLayout(header_layout)

        # --- 2. KEYBOARD PREVIEW CARD ---
        preview_card = QFrame()
        preview_card.setProperty("class", "cardFrame")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(10)

        p_header = QHBoxLayout()
        p_title = QLabel("Keyboard Lighting Preview")
        p_title.setProperty("class", "sectionTitle")
        p_header.addWidget(p_title)
        p_header.addStretch()

        self.lbl_status_pill = QLabel("APPLIED")
        self.lbl_status_pill.setStyleSheet(
            "background-color: #1e3a2f; color: #a6e3a1; "
            "border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
        )
        p_header.addWidget(self.lbl_status_pill)
        preview_layout.addLayout(p_header)

        # Custom keyboard preview widget
        self.preview_widget = KeyboardPreviewWidget(self)
        preview_layout.addWidget(self.preview_widget)

        # Current Settings Summary Strip
        strip_layout = QHBoxLayout()
        strip_layout.setSpacing(14)

        self.strip_color_dot = QLabel()
        self.strip_color_dot.setFixedSize(14, 14)
        self.strip_color_dot.setStyleSheet("background-color: #FF0000; border-radius: 7px;")
        strip_layout.addWidget(self.strip_color_dot)

        self.strip_color_label = QLabel("Color: Red (#FF0000)")
        self.strip_color_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #cdd6f4;")
        strip_layout.addWidget(self.strip_color_label)

        strip_layout.addStretch()

        self.strip_bright_label = QLabel("Brightness: Level 4 (100%)")
        self.strip_bright_label.setStyleSheet("font-size: 12px; color: #a6adc8;")
        strip_layout.addWidget(self.strip_bright_label)

        preview_layout.addLayout(strip_layout)
        main_layout.addWidget(preview_card)

        # --- 3. COLOR PALETTE CARD ---
        color_card = QFrame()
        color_card.setProperty("class", "cardFrame")
        color_layout = QVBoxLayout(color_card)
        color_layout.setContentsMargins(12, 12, 12, 12)
        color_layout.setSpacing(10)

        c_header = QLabel("Color Selection")
        c_header.setProperty("class", "sectionTitle")
        color_layout.addWidget(c_header)

        color_tabs = QTabWidget()

        # Tab A: Preset Swatches Grid
        tab_presets = QWidget()
        grid = QGridLayout(tab_presets)
        grid.setContentsMargins(8, 10, 8, 10)
        grid.setSpacing(8)

        self.swatch_buttons: List[ColorSwatchButton] = []
        cols = 4
        for idx, c in enumerate(SUPPORTED_COLORS):
            btn = ColorSwatchButton(c)
            btn.clicked.connect(lambda checked, col=c: self.select_preset(col))
            grid.addWidget(btn, idx // cols, idx % cols)
            self.swatch_buttons.append(btn)

        color_tabs.addTab(tab_presets, "Calibrated Presets (16)")

        # Tab B: Custom Color Picker & Hex Input
        tab_custom = QWidget()
        custom_layout = QVBoxLayout(tab_custom)
        custom_layout.setContentsMargins(12, 12, 12, 12)
        custom_layout.setSpacing(12)

        picker_row = QHBoxLayout()
        picker_row.setSpacing(12)

        self.btn_open_picker = QPushButton("Open Visual Color Picker...")
        self.btn_open_picker.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_picker.clicked.connect(self.open_color_dialog)
        picker_row.addWidget(self.btn_open_picker)

        picker_row.addWidget(QLabel("Hex:"))
        self.hex_input = QLineEdit("#FF0000")
        self.hex_input.setMaximumWidth(110)
        self.hex_input.textEdited.connect(self._on_hex_text_edited)
        picker_row.addWidget(self.hex_input)

        self.btn_apply_hex = QPushButton("Set Hex")
        self.btn_apply_hex.clicked.connect(self._on_apply_hex_clicked)
        picker_row.addWidget(self.btn_apply_hex)
        picker_row.addStretch()

        custom_layout.addLayout(picker_row)

        # Nearest firmware match info box
        self.match_box = QFrame()
        self.match_box.setStyleSheet(
            "background-color: #181825; border: 1px solid #313244; "
            "border-radius: 8px; padding: 10px;"
        )
        match_layout = QHBoxLayout(self.match_box)
        match_layout.setContentsMargins(8, 8, 8, 8)
        match_layout.setSpacing(12)

        self.custom_preview_dot = QLabel()
        self.custom_preview_dot.setFixedSize(28, 28)
        self.custom_preview_dot.setStyleSheet("background-color: #FF0000; border-radius: 14px; border: 1px solid #ffffff40;")
        match_layout.addWidget(self.custom_preview_dot)

        arrow_lbl = QLabel("➔")
        arrow_lbl.setStyleSheet("font-size: 16px; color: #89dceb;")
        match_layout.addWidget(arrow_lbl)

        self.firmware_match_dot = QLabel()
        self.firmware_match_dot.setFixedSize(28, 28)
        self.firmware_match_dot.setStyleSheet("background-color: #FF0000; border-radius: 14px; border: 1px solid #ffffff40;")
        match_layout.addWidget(self.firmware_match_dot)

        match_text_vbox = QVBoxLayout()
        self.lbl_match_title = QLabel("Firmware Preset: Red (#FF0000)")
        self.lbl_match_title.setStyleSheet("font-weight: bold; color: #cdd6f4;")
        self.lbl_match_desc = QLabel("Hardware controller applies closest calibrated color.")
        self.lbl_match_desc.setStyleSheet("font-size: 11px; color: #a6adc8;")
        match_text_vbox.addWidget(self.lbl_match_title)
        match_text_vbox.addWidget(self.lbl_match_desc)
        match_layout.addLayout(match_text_vbox)
        match_layout.addStretch()

        custom_layout.addWidget(self.match_box)

        # Quick Favorites Row
        fav_label = QLabel("Quick Favorites:")
        fav_label.setStyleSheet("font-weight: 600; font-size: 12px; color: #a6adc8;")
        custom_layout.addWidget(fav_label)

        fav_row = QHBoxLayout()
        fav_row.setSpacing(8)
        self.fav_buttons: List[QPushButton] = []
        saved_favs = self.config.get("custom_favorites", [])
        for f_hex in saved_favs[:8]:
            f_btn = QPushButton()
            f_btn.setFixedSize(32, 32)
            f_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            f_btn.setStyleSheet(f"background-color: {f_hex}; border-radius: 16px; border: 1px solid #ffffff30;")
            f_btn.setToolTip(f_hex)
            f_btn.clicked.connect(lambda checked, h=f_hex: self.select_hex(h))
            fav_row.addWidget(f_btn)
            self.fav_buttons.append(f_btn)
        fav_row.addStretch()
        custom_layout.addLayout(fav_row)

        color_tabs.addTab(tab_custom, "Custom Color & Hex")
        color_layout.addWidget(color_tabs)
        main_layout.addWidget(color_card)

        # --- 4. BRIGHTNESS & CONTROLS CARD ---
        control_card = QFrame()
        control_card.setProperty("class", "cardFrame")
        control_layout = QVBoxLayout(control_card)
        control_layout.setContentsMargins(12, 12, 12, 12)
        control_layout.setSpacing(12)

        b_header = QHBoxLayout()
        b_title = QLabel("Keyboard Brightness")
        b_title.setProperty("class", "sectionTitle")
        b_header.addWidget(b_title)
        b_header.addStretch()

        self.lbl_bright_val = QLabel("Level 4 (100% - Maximum)")
        self.lbl_bright_val.setStyleSheet("font-weight: bold; color: #38bdf8;")
        b_header.addWidget(self.lbl_bright_val)
        control_layout.addLayout(b_header)

        # Slider (0..4)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 4)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(1)
        self.slider.setValue(4)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        control_layout.addWidget(self.slider)

        # Discrete tick labels
        tick_row = QHBoxLayout()
        tick_labels = ["Off (0)", "25% (1)", "50% (2)", "75% (3)", "100% (4)"]
        for idx, t in enumerate(tick_labels):
            lbl = QLabel(t)
            lbl.setStyleSheet("font-size: 11px; color: #a6adc8;")
            if idx == 0:
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            elif idx == len(tick_labels) - 1:
                lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            else:
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tick_row.addWidget(lbl)
        control_layout.addLayout(tick_row)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.chk_instant = QCheckBox("Instant Apply")
        self.chk_instant.setChecked(bool(self.config.get("instant_apply", True)))
        self.chk_instant.toggled.connect(self._on_instant_toggled)
        actions_row.addWidget(self.chk_instant)

        actions_row.addStretch()

        self.btn_apply = QPushButton("Apply Settings")
        self.btn_apply.setProperty("class", "primaryButton")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self.apply_current_settings)
        actions_row.addWidget(self.btn_apply)

        control_layout.addLayout(actions_row)
        main_layout.addWidget(control_card)

        # --- 5. SYSTEM DIAGNOSTICS & SETTINGS CARD ---
        extra_card = QFrame()
        extra_card.setProperty("class", "cardFrame")
        extra_layout = QVBoxLayout(extra_card)
        extra_layout.setContentsMargins(12, 12, 12, 12)
        extra_layout.setSpacing(10)

        extra_tabs = QTabWidget()

        # Tab: Live Diagnostics
        tab_diag = QWidget()
        d_layout = QVBoxLayout(tab_diag)
        d_layout.setContentsMargins(8, 8, 8, 8)
        d_layout.setSpacing(6)

        self.lbl_diag_dev = QLabel("Device Node: checking...")
        self.lbl_diag_acpi = QLabel("ACPI Status: checking...")
        self.lbl_diag_driver = QLabel("Driver Info: checking...")
        self.lbl_diag_hw = QLabel("Hardware Output: UNVERIFIED (Confirm physically)")
        self.lbl_diag_hw.setStyleSheet("color: #fab387; font-size: 11px;")

        for lbl in (self.lbl_diag_dev, self.lbl_diag_acpi, self.lbl_diag_driver, self.lbl_diag_hw):
            lbl.setStyleSheet("font-size: 11px; color: #a6adc8;")
            d_layout.addWidget(lbl)

        d_btn_row = QHBoxLayout()
        d_btn_row.addStretch()
        btn_refresh_diag = QPushButton("Refresh Status")
        btn_refresh_diag.clicked.connect(self.refresh_diagnostics)
        d_btn_row.addWidget(btn_refresh_diag)
        d_layout.addLayout(d_btn_row)

        extra_tabs.addTab(tab_diag, "Driver Status")

        # Tab: Preferences & Autostart
        tab_settings = QWidget()
        s_layout = QVBoxLayout(tab_settings)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(8)

        self.chk_autostart = QCheckBox("Restore keyboard lighting automatically on desktop login")
        self.chk_autostart.setChecked(bool(self.config.get("restore_on_login", False)))
        self.chk_autostart.toggled.connect(self._on_autostart_toggled)
        s_layout.addWidget(self.chk_autostart)

        self.chk_tray_close = QCheckBox("Minimize to system tray instead of exiting on window close")
        self.chk_tray_close.setChecked(bool(self.config.get("minimize_to_tray", True)))
        self.chk_tray_close.toggled.connect(lambda v: self.config.set("minimize_to_tray", v))
        s_layout.addWidget(self.chk_tray_close)

        desc_lbl = QLabel("Acer ALG AL15G-52 RGB Keyboard Driver v0.1.3")
        desc_lbl.setStyleSheet("font-size: 10px; color: #6c7086;")
        s_layout.addWidget(desc_lbl)

        extra_tabs.addTab(tab_settings, "Preferences")
        extra_layout.addWidget(extra_tabs)
        main_layout.addWidget(extra_card)

    def init_tray(self):
        self.tray = AlgTrayIcon(self.icon_path, self)
        self.tray.color_selected.connect(self._on_tray_color_selected)
        self.tray.brightness_selected.connect(self._on_tray_brightness_selected)
        self.tray.power_toggled.connect(self.toggle_power)
        self.tray.toggle_window_requested.connect(self.toggle_window_visibility)
        self.tray.quit_requested.connect(self.force_quit)
        self.tray.show()

    def restore_initial_state(self):
        diag = read_diagnostics()

        # Check if driver reported an active color & brightness
        active_color_name = diag.get("last_color", "none")
        active_bright = diag.get("last_brightness", -1)

        if active_color_name in ("none", "unknown", "") or active_color_name == "off":
            # Fall back to saved config
            saved_color_name = self.config.get("last_color", "red")
            matched = get_color(saved_color_name) or SUPPORTED_COLORS[0]
            self.current_color = matched
            self.current_brightness = int(self.config.get("last_brightness", 4))
            self.power_on = (active_color_name != "off")
        else:
            matched = get_color(active_color_name) or SUPPORTED_COLORS[0]
            self.current_color = matched
            self.current_brightness = active_bright if active_bright >= 0 else 4
            self.power_on = True

        self._update_ui_state(is_applied=True)
        self.refresh_diagnostics()

    def select_preset(self, color_item: AlgColor):
        self.current_color = color_item
        self.power_on = True
        self.hex_input.setText(color_item.hex_code)
        self._update_ui_state(is_applied=False)

        if self.chk_instant.isChecked():
            self.apply_timer.start()

    def select_hex(self, hex_code: str):
        self.hex_input.setText(hex_code)
        self._on_apply_hex_clicked()

    def _on_hex_text_edited(self, text: str):
        rgb = hex_to_rgb(text)
        if rgb:
            nearest = find_nearest_preset(*rgb)
            self.current_preview_dot.setStyleSheet(f"background-color: {text}; border-radius: 14px; border: 1px solid #ffffff40;")
            self.firmware_match_dot.setStyleSheet(f"background-color: {nearest.hex_code}; border-radius: 14px; border: 1px solid #ffffff40;")
            self.lbl_match_title.setText(f"Firmware Preset: {nearest.label} ({nearest.hex_code})")

    def _on_apply_hex_clicked(self):
        rgb = hex_to_rgb(self.hex_input.text())
        if not rgb:
            QMessageBox.warning(self, "Invalid Hex Color", "Please enter a valid hex color code (e.g. #FF0000).")
            return

        nearest = find_nearest_preset(*rgb)
        self.select_preset(nearest)

    def open_color_dialog(self):
        initial = QColor(self.current_color.r, self.current_color.g, self.current_color.b)
        dialog = QColorDialog(initial, self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
        if dialog.exec() == QColorDialog.DialogCode.Accepted:
            chosen = dialog.selectedColor()
            hex_str = chosen.name().upper()
            self.hex_input.setText(hex_str)
            self._on_apply_hex_clicked()

    def _on_slider_value_changed(self, val: int):
        self.current_brightness = val
        self.power_on = (val > 0)
        self._update_brightness_text(val)
        self.preview_widget.set_lighting(self.current_color, self.current_brightness, is_applied=False)

        if self.chk_instant.isChecked():
            self.apply_timer.start()
        else:
            self.set_applied_indicator(False)

    def _update_brightness_text(self, val: int):
        labels = {
            0: "Level 0 (Off)",
            1: "Level 1 (25% - Low)",
            2: "Level 2 (50% - Medium)",
            3: "Level 3 (75% - High)",
            4: "Level 4 (100% - Maximum)"
        }
        self.lbl_bright_val.setText(labels.get(val, f"Level {val}"))
        self.strip_bright_label.setText(f"Brightness: {labels.get(val, f'Level {val}')}")

    def toggle_power(self):
        if self.power_on:
            # Turn off
            success, msg = turn_off()
            if success:
                self.power_on = False
                self.preview_widget.set_lighting(COLOR_OFF, 0, is_applied=True)
                self.btn_power_toggle.setText("Turn On")
                self.btn_power_toggle.setStyleSheet("background-color: #1e3a2f; color: #a6e3a1; border: 1px solid #10b981;")
                self.set_applied_indicator(True, is_off=True)
                self.tray.set_state(COLOR_OFF, 0)
                self.refresh_diagnostics()
            else:
                QMessageBox.critical(self, "Power Off Failed", f"Could not power off lighting:\n{msg}")
        else:
            # Turn on / restore
            self.power_on = True
            if self.current_brightness == 0:
                self.current_brightness = 4
                self.slider.setValue(4)
            self.apply_current_settings()

    def apply_current_settings(self):
        if not self.power_on or self.current_brightness == 0:
            self.toggle_power()
            return

        success, msg = apply_color(self.current_color.name, self.current_brightness)
        if success:
            self.set_applied_indicator(True)
            self.config.set("last_color", self.current_color.name)
            self.config.set("last_brightness", self.current_brightness)

            # Update autostart if configured
            if self.config.get("restore_on_login", False):
                cli = find_cli_path() or "alg-rgb"
                self.config.set_autostart(True, self.current_color.name, self.current_brightness, cli)

            self.refresh_diagnostics()
        else:
            self.set_applied_indicator(False)
            QMessageBox.critical(
                self,
                "Failed to Apply RGB Lighting",
                f"Error applying color '{self.current_color.name}':\n\n{msg}\n\n"
                f"Make sure the 'alg_rgb' module is loaded and your user belongs to the 'alg-rgb' group."
            )

    def _on_debounced_apply(self):
        if self.chk_instant.isChecked():
            self.apply_current_settings()

    def _update_ui_state(self, is_applied: bool):
        # Update preset swatches selection styling
        for btn in self.swatch_buttons:
            btn.update_selection_style(btn.color_item.name == self.current_color.name)

        # Update summary strip
        self.strip_color_dot.setStyleSheet(f"background-color: {self.current_color.hex_code}; border-radius: 7px;")
        self.strip_color_label.setText(f"Color: {self.current_color.label} ({self.current_color.hex_code})")
        self._update_brightness_text(self.current_brightness)

        # Update custom match preview
        self.custom_preview_dot.setStyleSheet(f"background-color: {self.current_color.hex_code}; border-radius: 14px; border: 1px solid #ffffff40;")
        self.firmware_match_dot.setStyleSheet(f"background-color: {self.current_color.hex_code}; border-radius: 14px; border: 1px solid #ffffff40;")
        self.lbl_match_title.setText(f"Firmware Preset: {self.current_color.label} ({self.current_color.hex_code})")

        # Slider and power toggle button
        self.slider.blockSignals(True)
        self.slider.setValue(self.current_brightness)
        self.slider.blockSignals(False)

        if self.power_on:
            self.btn_power_toggle.setText("Turn Off")
            self.btn_power_toggle.setStyleSheet("")
            self.btn_power_toggle.setProperty("class", "offButton")
        else:
            self.btn_power_toggle.setText("Turn On")
            self.btn_power_toggle.setStyleSheet("background-color: #1e3a2f; color: #a6e3a1; border: 1px solid #10b981;")

        # Update keyboard preview widget
        self.preview_widget.set_lighting(self.current_color, self.current_brightness, is_applied)
        self.tray.set_state(self.current_color, self.current_brightness if self.power_on else 0)
        self.set_applied_indicator(is_applied, is_off=not self.power_on)

    def set_applied_indicator(self, applied: bool, is_off: bool = False):
        self.is_applied = applied
        if is_off:
            self.lbl_status_pill.setText("OFF")
            self.lbl_status_pill.setStyleSheet("background-color: #313244; color: #a6adc8; border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold;")
        elif applied:
            self.lbl_status_pill.setText("APPLIED")
            self.lbl_status_pill.setStyleSheet("background-color: #1e3a2f; color: #a6e3a1; border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold;")
        else:
            self.lbl_status_pill.setText("PENDING")
            self.lbl_status_pill.setStyleSheet("background-color: #44331d; color: #fab387; border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold;")
        self.preview_widget.set_applied_state(applied)

    def _on_instant_toggled(self, checked: bool):
        self.config.set("instant_apply", checked)
        self.btn_apply.setVisible(not checked)

    def _on_autostart_toggled(self, checked: bool):
        cli = find_cli_path() or "alg-rgb"
        self.config.set_autostart(checked, self.current_color.name, self.current_brightness, cli)

    def _on_tray_color_selected(self, color_name: str):
        c = get_color(color_name)
        if c:
            self.select_preset(c)
            self.apply_current_settings()

    def _on_tray_brightness_selected(self, level: int):
        self.slider.setValue(level)
        self.apply_current_settings()

    def toggle_window_visibility(self):
        if self.isVisible():
            if self.isMinimized():
                self.showNormal()
                self.activateWindow()
            else:
                self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def refresh_diagnostics(self):
        diag = read_diagnostics()
        dev_ok = diag["device_exists"] and diag["device_writable"]
        dev_str = "AVAILABLE & WRITABLE (/dev/alg_rgb)" if dev_ok else "NOT ACCESSIBLE (/dev/alg_rgb)"
        self.lbl_diag_dev.setText(f"Device Node: {dev_str}")
        self.lbl_diag_dev.setStyleSheet(f"font-size: 11px; color: {'#a6e3a1' if dev_ok else '#f38ba8'};")

        acpi_desc = diag.get("last_acpi_desc", "Unknown")
        self.lbl_diag_acpi.setText(f"Last ACPI Call: {acpi_desc}")

        drv_ver = diag.get("driver_version", "unknown")
        mod_loaded = diag.get("module_loaded", False)
        self.lbl_diag_driver.setText(f"Driver Version: {drv_ver} (Module loaded: {'yes' if mod_loaded else 'no'})")

        hw_conf = diag.get("hardware_confirmation", "UNVERIFIED")
        self.lbl_diag_hw.setText(f"Hardware Status: {hw_conf}")

    def closeEvent(self, event):
        if self.config.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Acer ALG RGB",
                "Application minimized to system tray.",
                QSystemTrayIcon.MessageIcon.Information,
                1500
            )
        else:
            event.accept()

    def force_quit(self):
        self.diag_timer.stop()
        self.apply_timer.stop()
        QApplication.quit()
