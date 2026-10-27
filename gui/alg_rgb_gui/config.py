"""
Configuration and preferences manager for Acer ALG RGB GUI.
Saves settings to ~/.config/alg-rgb/config.json and manages optional XDG autostart.
"""

import os
import json
from typing import Dict, Any, List

CONFIG_DIR = os.path.expanduser("~/.config/alg-rgb")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "alg-rgb-restore.desktop")

DEFAULT_CONFIG: Dict[str, Any] = {
    "last_color": "red",
    "last_brightness": 4,
    "instant_apply": True,
    "minimize_to_tray": True,
    "restore_on_login": False,
    "fan_mode": "auto",
    "custom_cpu_duty": 50,
    "custom_gpu_duty": 50,
    "sync_fans": True,
    "custom_favorites": [
        "#FF0000", "#FF7F00", "#FFFF00", "#00FF00",
        "#00FFC8", "#0000C8", "#7F00C8", "#FF00C8"
    ]
}


class ConfigManager:
    def __init__(self):
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.config.update(data)
            except Exception:
                pass

    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save()

    def set_autostart(self, enabled: bool, color: str, brightness: int, cli_path: str):
        """Enable or disable XDG autostart to restore lighting on session login."""
        self.set("restore_on_login", enabled)

        if not enabled:
            if os.path.exists(AUTOSTART_FILE):
                try:
                    os.remove(AUTOSTART_FILE)
                except Exception:
                    pass
            return

        try:
            os.makedirs(AUTOSTART_DIR, exist_ok=True)
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=Acer ALG RGB Lighting Restore
Comment=Restores keyboard RGB lighting on login
Exec={cli_path} {color.strip().lower()} {int(brightness)}
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
"""
            with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
                f.write(desktop_content)
        except Exception:
            pass
