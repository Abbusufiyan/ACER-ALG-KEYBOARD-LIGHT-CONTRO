"""
System Tray Integration for KDE Plasma 6.
Provides quick color swatches, brightness controls, and toggle actions from the taskbar.
"""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import pyqtSignal, QByteArray
from PyQt6.QtSvg import QSvgRenderer

from .colors import SUPPORTED_COLORS, AlgColor, COLOR_OFF


class AlgTrayIcon(QSystemTrayIcon):
    # Signals to communicate user actions back to main window
    color_selected = pyqtSignal(str)       # color_name
    brightness_selected = pyqtSignal(int)  # 0..4
    power_toggled = pyqtSignal()
    toggle_window_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, icon_path: str, parent=None):
        super().__init__(parent)
        self._icon_path = icon_path
        self._current_color: AlgColor = SUPPORTED_COLORS[0]
        self._current_brightness: int = 4
        self._power_on: bool = True

        self.update_tray_icon()
        self.build_menu()

        self.activated.connect(self._on_activated)

    def set_state(self, color: AlgColor, brightness: int):
        self._current_color = color
        self._current_brightness = brightness
        self._power_on = (color.name != "off" and brightness > 0)
        self.update_tray_icon()
        self.update_tooltip()
        self.build_menu()

    def update_tooltip(self):
        if self._power_on:
            tip = f"Acer ALG RGB\nColor: {self._current_color.label} ({self._current_color.hex_code})\nBrightness: Level {self._current_brightness}/4"
        else:
            tip = "Acer ALG RGB\nLighting: Powered Off"
        self.setToolTip(tip)

    def update_tray_icon(self):
        """Draw an icon dynamically tinted with current RGB color."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base icon shape (dark rounded chassis)
        painter.setBrush(QColor("#181926"))
        painter.setPen(QColor("#313244"))
        painter.drawRoundedRect(4, 12, 56, 40, 10, 10)

        # RGB Underglow dot / bar
        if self._power_on and self._current_brightness > 0:
            c = QColor(self._current_color.r, self._current_color.g, self._current_color.b)
            painter.setBrush(c)
            painter.setPen(c)
            # Glowing keyboard keys matrix representation
            painter.drawRoundedRect(12, 20, 10, 8, 2, 2)
            painter.drawRoundedRect(27, 20, 10, 8, 2, 2)
            painter.drawRoundedRect(42, 20, 10, 8, 2, 2)
            painter.drawRoundedRect(16, 34, 32, 8, 3, 3)
        else:
            # Dim unlit keys
            painter.setBrush(QColor("#45475a"))
            painter.setPen(QColor("#313244"))
            painter.drawRoundedRect(12, 20, 10, 8, 2, 2)
            painter.drawRoundedRect(27, 20, 10, 8, 2, 2)
            painter.drawRoundedRect(42, 20, 10, 8, 2, 2)
            painter.drawRoundedRect(16, 34, 32, 8, 3, 3)

        painter.end()
        self.setIcon(QIcon(pixmap))

    def build_menu(self):
        menu = QMenu()

        # Header title
        title_action = menu.addAction("Acer ALG RGB Controller")
        title_action.setEnabled(False)
        menu.addSeparator()

        # Quick Colors Submenu
        color_menu = menu.addMenu("Presets")
        quick_presets = [
            "red", "orange", "yellow", "green", "cyan",
            "blue", "violet", "magenta", "white"
        ]
        for c_name in quick_presets:
            from .colors import get_color
            color_obj = get_color(c_name)
            if not color_obj:
                continue

            # Small color swatch icon
            swatch_px = QPixmap(16, 16)
            swatch_px.fill(QColor(color_obj.r, color_obj.g, color_obj.b))
            swatch_icon = QIcon(swatch_px)

            action = color_menu.addAction(swatch_icon, color_obj.label)
            action.triggered.connect(lambda checked, name=c_name: self.color_selected.emit(name))

        # Brightness Submenu
        bright_menu = menu.addMenu("Brightness")
        levels = [
            (4, "Level 4 (100% - Maximum)"),
            (3, "Level 3 (75% - High)"),
            (2, "Level 2 (50% - Medium)"),
            (1, "Level 1 (25% - Low)"),
            (0, "Level 0 (Off)")
        ]
        for lvl, label in levels:
            action = bright_menu.addAction(label)
            if self._current_brightness == lvl:
                action.setText(f"✓ {label}")
            action.triggered.connect(lambda checked, b=lvl: self.brightness_selected.emit(b))

        menu.addSeparator()

        # Power Toggle
        if self._power_on:
            power_act = menu.addAction("Turn Off Lighting")
        else:
            power_act = menu.addAction("Turn On Lighting")
        power_act.triggered.connect(self.power_toggled.emit)

        menu.addSeparator()

        # Window controls
        open_act = menu.addAction("Open Controller")
        open_act.triggered.connect(self.toggle_window_requested.emit)

        quit_act = menu.addAction("Quit")
        quit_act.triggered.connect(self.quit_requested.emit)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window_requested.emit()
