"""
Modern Dark Theme QSS Stylesheet and Palette for Acer ALG RGB GUI.
Designed to integrate seamlessly with KDE Plasma 6 Breeze Dark and modern Wayland desktops.
"""

DARK_STYLESHEET = """
QMainWindow {
    background-color: #14151f;
    color: #cdd6f4;
}

QWidget {
    font-family: "Noto Sans", "Cantarell", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #cdd6f4;
    outline: none;
}

/* Scroll area */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: #181926;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #45475a;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Cards and Containers */
QFrame.cardFrame {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 12px;
    padding: 12px;
}

QFrame.cardFrame:hover {
    border: 1px solid #45475a;
}

/* Group Headers */
QLabel.sectionTitle {
    font-size: 14px;
    font-weight: bold;
    color: #f5e0dc;
    margin-bottom: 4px;
}

QLabel.sectionDesc {
    font-size: 11px;
    color: #a6adc8;
    margin-bottom: 8px;
}

/* Standard Buttons */
QPushButton {
    background-color: #27293d;
    color: #cdd6f4;
    border: 1px solid #3d405b;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #363954;
    border-color: #585b70;
}

QPushButton:pressed {
    background-color: #1e2032;
}

QPushButton:disabled {
    background-color: #1b1c28;
    color: #6c7086;
    border-color: #262838;
}

/* Primary Action Button */
QPushButton.primaryButton {
    background-color: #38bdf8;
    color: #0f172a;
    border: none;
    font-weight: bold;
    padding: 9px 18px;
    border-radius: 8px;
}

QPushButton.primaryButton:hover {
    background-color: #7dd3fc;
}

QPushButton.primaryButton:pressed {
    background-color: #0284c7;
}

/* Danger / Off Button */
QPushButton.offButton {
    background-color: #312128;
    color: #f38ba8;
    border: 1px solid #582a38;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}

QPushButton.offButton:hover {
    background-color: #4a2936;
    border-color: #f38ba8;
}

QPushButton.offButton:pressed {
    background-color: #26161f;
}

/* Slider */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #313244;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #818cf8);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 3px solid #38bdf8;
    width: 20px;
    height: 20px;
    margin: -7px 0;
    border-radius: 10px;
}

QSlider::handle:horizontal:hover {
    background: #e0f2fe;
    border-color: #7dd3fc;
    transform: scale(1.1);
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 10px;
    background-color: #181825;
    top: -1px;
}

QTabBar::tab {
    background: #181926;
    color: #a6adc8;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 7px 16px;
    margin-right: 4px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background: #1e1e2e;
    color: #38bdf8;
    border-color: #38bdf8;
    border-bottom: 2px solid #1e1e2e;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background: #24273a;
    color: #cdd6f4;
}

/* Line Edit / Input */
QLineEdit {
    background-color: #181926;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 6px 10px;
    color: #cdd6f4;
    selection-background-color: #38bdf8;
    selection-color: #0f172a;
}

QLineEdit:focus {
    border: 1px solid #38bdf8;
}

/* Checkbox */
QCheckBox {
    spacing: 8px;
    color: #cdd6f4;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #45475a;
    background-color: #181926;
}

QCheckBox::indicator:checked {
    background-color: #38bdf8;
    border-color: #38bdf8;
    image: none;
}

QCheckBox::indicator:hover {
    border-color: #89dceb;
}

/* Tooltips */
QToolTip {
    background-color: #181926;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}
"""
