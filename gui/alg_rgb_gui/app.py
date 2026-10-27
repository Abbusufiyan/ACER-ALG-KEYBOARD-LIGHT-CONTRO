"""
Application lifecycle, styling, signal handling, and initialization.
"""

import sys
import os
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from .main_window import AcerAlgRgbWindow
from .style import DARK_STYLESHEET
from .config import ConfigManager

APP_ID = "alg-rgb-gui"
APP_NAME = "Acer ALG RGB"
APP_VERSION = "0.1.3"


def main():
    # Enable Ctrl+C to terminate application gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName(APP_ID)

    # Apply modern dark theme stylesheet
    app.setStyleSheet(DARK_STYLESHEET)

    # Locate app icon across possible standard paths
    icon_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "alg-rgb-gui.png"),
        "/usr/local/share/alg-rgb-gui/assets/alg-rgb-gui.png",
        "/usr/local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png",
        os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png")
    ]
    icon_png = next((p for p in icon_candidates if os.path.exists(p)), "")

    window = AcerAlgRgbWindow(icon_png)

    # Check command-line options
    start_minimized = "--minimized" in sys.argv or "-m" in sys.argv

    if not start_minimized:
        window.show()
    else:
        window.hide()

    # Python signal wakeup timer so Qt processes Unix signals
    sig_timer = QTimer()
    sig_timer.start(500)
    sig_timer.timeout.connect(lambda: None)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
