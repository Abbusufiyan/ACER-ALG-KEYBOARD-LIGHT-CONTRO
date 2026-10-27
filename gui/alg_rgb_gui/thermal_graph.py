"""
Real-time animated temperature history graph widget.
Plots rolling 60-second telemetry curves for CPU and GPU with thermal safety thresholds.
"""

from collections import deque
from typing import Deque, Tuple
import time

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QPolygonF
from PyQt6.QtCore import Qt, QRectF, QPointF


class TemperatureHistoryGraph(QWidget):
    def __init__(self, parent=None, max_points: int = 60):
        super().__init__(parent)
        self.setMinimumSize(420, 150)
        self.setMaximumHeight(200)
        self.max_points = max_points

        # Data queues: (cpu_temp, gpu_temp)
        self.history: Deque[Tuple[float, float]] = deque(maxlen=max_points)
        # Pre-fill with starting baseline
        for _ in range(max_points):
            self.history.append((45.0, 40.0))

        self.last_cpu: float = 45.0
        self.last_gpu: float = 40.0

    def add_sample(self, cpu_temp: float, gpu_temp: float):
        self.last_cpu = max(20.0, min(115.0, cpu_temp))
        self.last_gpu = max(20.0, min(115.0, gpu_temp)) if gpu_temp > 0 else 0.0
        self.history.append((self.last_cpu, self.last_gpu))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        # Background frame
        margin_left = 38.0
        margin_right = 14.0
        margin_top = 22.0
        margin_bottom = 22.0

        plot_w = w - margin_left - margin_right
        plot_h = h - margin_top - margin_bottom

        # 1. Dark canvas background
        bg_rect = QRectF(margin_left, margin_top, plot_w, plot_h)
        painter.setPen(QPen(QColor("#313244"), 1))
        painter.setBrush(QColor("#11111b"))
        painter.drawRoundedRect(bg_rect, 6, 6)

        # Temperature range on Y-axis: 30°C to 105°C
        min_temp = 30.0
        max_temp = 105.0
        temp_range = max_temp - min_temp

        def temp_to_y(temp: float) -> float:
            clamped = max(min_temp, min(max_temp, temp))
            ratio = (clamped - min_temp) / temp_range
            return margin_top + plot_h - (ratio * plot_h)

        # 2. Horizontal Grid Lines & Labels
        painter.setFont(QFont("Noto Sans", 8))
        grid_temps = [
            (100.0, "#f38ba8", "100°"),
            (85.0, "#fab387", "85°"),
            (65.0, "#45475a", "65°"),
            (45.0, "#313244", "45°")
        ]

        for t_val, color_hex, lbl_text in grid_temps:
            y_pos = temp_to_y(t_val)
            # Label on left
            painter.setPen(QColor(color_hex))
            painter.drawText(QRectF(2, y_pos - 7, margin_left - 6, 14), Qt.AlignmentFlag.AlignRight, lbl_text)

            # Dashed grid line
            pen = QPen(QColor(color_hex))
            pen.setStyle(Qt.PenStyle.DashLine if t_val >= 85 else Qt.PenStyle.DotLine)
            pen.setWidthF(0.8)
            painter.setPen(pen)
            painter.drawLine(QPointF(margin_left, y_pos), QPointF(margin_left + plot_w, y_pos))

        # 3. Time labels on bottom
        painter.setPen(QColor("#6c7086"))
        painter.drawText(QRectF(margin_left, h - 16, 40, 14), Qt.AlignmentFlag.AlignLeft, "-60s")
        painter.drawText(QRectF(margin_left + plot_w / 2 - 20, h - 16, 40, 14), Qt.AlignmentFlag.AlignCenter, "-30s")
        painter.drawText(QRectF(margin_left + plot_w - 40, h - 16, 40, 14), Qt.AlignmentFlag.AlignRight, "Now")

        # 4. Draw GPU Temperature Curve (Emerald)
        if any(g > 0 for _, g in self.history):
            gpu_points = []
            x_step = plot_w / float(self.max_points - 1)
            for idx, (_, g_val) in enumerate(self.history):
                x = margin_left + idx * x_step
                y = temp_to_y(g_val if g_val > 0 else min_temp)
                gpu_points.append(QPointF(x, y))

            # Fill area below curve
            if gpu_points:
                poly = QPolygonF(gpu_points)
                poly.append(QPointF(margin_left + plot_w, margin_top + plot_h))
                poly.append(QPointF(margin_left, margin_top + plot_h))
                gpu_grad = QLinearGradient(0, margin_top, 0, margin_top + plot_h)
                gpu_grad.setColorAt(0.0, QColor(166, 227, 161, 45))
                gpu_grad.setColorAt(1.0, QColor(166, 227, 161, 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(gpu_grad))
                painter.drawPolygon(poly)

                # Draw Curve Line
                gpu_pen = QPen(QColor("#a6e3a1"))
                gpu_pen.setWidthF(1.8)
                painter.setPen(gpu_pen)
                for i in range(len(gpu_points) - 1):
                    painter.drawLine(gpu_points[i], gpu_points[i + 1])

        # 5. Draw CPU Temperature Curve (Sky Blue)
        cpu_points = []
        x_step = plot_w / float(self.max_points - 1)
        for idx, (c_val, _) in enumerate(self.history):
            x = margin_left + idx * x_step
            y = temp_to_y(c_val)
            cpu_points.append(QPointF(x, y))

        if cpu_points:
            poly = QPolygonF(cpu_points)
            poly.append(QPointF(margin_left + plot_w, margin_top + plot_h))
            poly.append(QPointF(margin_left, margin_top + plot_h))
            cpu_grad = QLinearGradient(0, margin_top, 0, margin_top + plot_h)
            cpu_grad.setColorAt(0.0, QColor(56, 189, 248, 55))
            cpu_grad.setColorAt(1.0, QColor(56, 189, 248, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(cpu_grad))
            painter.drawPolygon(poly)

            # Draw Curve Line
            cpu_pen = QPen(QColor("#38bdf8"))
            cpu_pen.setWidthF(2.0)
            painter.setPen(cpu_pen)
            for i in range(len(cpu_points) - 1):
                painter.drawLine(cpu_points[i], cpu_points[i + 1])

        # 6. Top Legend Strip
        painter.setFont(QFont("Noto Sans", 8, QFont.Weight.DemiBold))

        # CPU Legend
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#38bdf8"))
        painter.drawRoundedRect(QRectF(margin_left + 6, 6, 10, 10), 2, 2)
        painter.setPen(QColor("#cdd6f4"))
        painter.drawText(margin_left + 22, 15, f"CPU Package: {self.last_cpu:.0f}°C")

        # GPU Legend
        if self.last_gpu > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#a6e3a1"))
            painter.drawRoundedRect(QRectF(margin_left + 150, 6, 10, 10), 2, 2)
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(margin_left + 166, 15, f"RTX 2050: {self.last_gpu:.0f}°C")

        # Live dot indicator on current points
        if cpu_points:
            last_pt = cpu_points[-1]
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QColor("#38bdf8"))
            painter.drawEllipse(last_pt, 3.5, 3.5)

        painter.end()
