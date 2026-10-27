"""
Custom interactive keyboard RGB lighting preview widget for Acer ALG laptops.
Paints a stylized laptop keyboard chassis with dynamic per-key and ambient LED glow.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QFont
from PyQt6.QtCore import Qt, QRectF, pyqtProperty

from .colors import AlgColor, SUPPORTED_COLORS, COLOR_OFF


class KeyboardPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(460, 180)
        self.setMaximumHeight(230)

        # Current state
        self._color: AlgColor = SUPPORTED_COLORS[0]  # Default red
        self._brightness: int = 4                    # 0 to 4
        self._is_applied: bool = True
        self._power_on: bool = True

        self.setToolTip("Acer ALG AL15G-52 Built-in Keyboard Lighting Preview")

    def set_lighting(self, color: AlgColor, brightness: int, is_applied: bool = True):
        """Update preview state and trigger repaint."""
        self._color = color
        self._brightness = max(0, min(4, brightness))
        self._power_on = (color.name != "off" and self._brightness > 0)
        self._is_applied = is_applied
        self.update()

    def set_applied_state(self, is_applied: bool):
        self._is_applied = is_applied
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Background Laptop Chassis (Anodized dark aluminum deck)
        deck_rect = QRectF(10, 10, w - 20, h - 20)
        deck_grad = QLinearGradient(0, 0, 0, h)
        deck_grad.setColorAt(0.0, QColor("#1e1e2e"))
        deck_grad.setColorAt(1.0, QColor("#14151f"))

        painter.setPen(QPen(QColor("#313244"), 2))
        painter.setBrush(QBrush(deck_grad))
        painter.drawRoundedRect(deck_rect, 14, 14)

        # 2. Keyboard Well / Recessed Well
        tray_rect = QRectF(22, 22, w - 44, h - 44)
        painter.setPen(QPen(QColor("#242538"), 1.5))
        painter.setBrush(QColor("#11111b"))
        painter.drawRoundedRect(tray_rect, 10, 10)

        # Determine glow color and alpha from brightness
        # Brightness 0: 0, 1: 55, 2: 110, 3: 175, 4: 255
        alpha_map = {0: 0, 1: 65, 2: 120, 3: 185, 4: 255}
        glow_alpha = alpha_map.get(self._brightness, 0) if self._power_on else 0

        glow_color = QColor(self._color.r, self._color.g, self._color.b, glow_alpha)

        # 3. Ambient Keyboard Bed Glow
        if self._power_on and glow_alpha > 0:
            rad_grad = QRadialGradient(w / 2.0, h / 2.0, w / 1.7)
            rad_grad.setColorAt(0.0, QColor(self._color.r, self._color.g, self._color.b, int(glow_alpha * 0.45)))
            rad_grad.setColorAt(0.65, QColor(self._color.r, self._color.g, self._color.b, int(glow_alpha * 0.18)))
            rad_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(rad_grad))
            painter.drawRoundedRect(tray_rect, 10, 10)

        # 4. Draw Simplified Laptop Keyboard Matrix
        # Calculate rows based on tray dimensions
        tw = tray_rect.width()
        th = tray_rect.height()

        num_rows = 5
        row_height = (th - 16) / num_rows
        pad_x = 30
        pad_y = 28

        # Define row key distributions
        row_configs = [
            # Row 0: Function row (14 keys)
            [1.0] * 14,
            # Row 1: Number row (Backspace at end)
            [1.0] * 12 + [2.0],
            # Row 2: Tab + QWERTY + Return
            [1.5] + [1.0] * 11 + [1.5],
            # Row 3: Caps + ASDF + Enter
            [1.8] + [1.0] * 10 + [2.2],
            # Row 4: Modifiers + Spacebar + Arrows
            [1.4, 1.2, 1.2, 6.2, 1.0, 1.0, 1.0, 1.0]
        ]

        for r_idx, row_weights in enumerate(row_configs):
            total_weight = sum(row_weights)
            key_y = pad_y + r_idx * row_height + 2
            curr_x = pad_x
            usable_w = tw - 16
            gap = 3.5

            for weight in row_weights:
                kw = (weight / total_weight) * usable_w - gap
                if kw < 4:
                    kw = 4
                key_rect = QRectF(curr_x, key_y, kw, row_height - gap)

                # Key Underglow
                if self._power_on and glow_alpha > 0:
                    underglow = QColor(self._color.r, self._color.g, self._color.b, int(glow_alpha * 0.6))
                    painter.setPen(QPen(underglow, 1.5))
                else:
                    painter.setPen(QPen(QColor("#27293d"), 1))

                # Keycap body
                painter.setBrush(QColor("#181926"))
                painter.drawRoundedRect(key_rect, 4, 4)

                curr_x += kw + gap

        # 5. Status Badges & Info Text
        painter.setFont(QFont("Noto Sans", 9, QFont.Weight.DemiBold))

        # Power OFF Banner if off
        if not self._power_on:
            painter.setPen(QColor("#6c7086"))
            painter.drawText(
                QRectF(0, h / 2.0 - 12, w, 24),
                Qt.AlignmentFlag.AlignCenter,
                "LIGHTING POWERED OFF"
            )

        # Top-right Pill Badge: APPLIED (Green) vs PENDING (Amber) vs OFF (Gray)
        badge_w = 78
        badge_h = 22
        badge_x = w - badge_w - 24
        badge_y = 16

        if not self._power_on:
            b_bg = QColor("#313244")
            b_fg = QColor("#a6adc8")
            b_text = "OFF"
        elif self._is_applied:
            b_bg = QColor("#1e3a2f")
            b_fg = QColor("#a6e3a1")
            b_text = "APPLIED"
        else:
            b_bg = QColor("#44331d")
            b_fg = QColor("#fab387")
            b_text = "PENDING"

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(b_bg)
        painter.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 6, 6)

        painter.setPen(b_fg)
        painter.setFont(QFont("Noto Sans", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(badge_x, badge_y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, b_text)

        # Bottom-left: Model & Hardware note
        painter.setFont(QFont("Noto Sans", 8))
        painter.setPen(QColor("#585b70"))
        painter.drawText(
            QRectF(26.0, float(h - 22), float(w - 52), 16.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Acer ALG AL15G-52 • Software Preview"
        )

        painter.end()
