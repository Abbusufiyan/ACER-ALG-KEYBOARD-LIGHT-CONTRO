#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
set -e

if [ "$(id -u)" -eq 0 ]; then
    echo "[*] Removing Acer ALG RGB GUI system-wide..."

    rm -f /usr/local/bin/alg-rgb-gui
    rm -rf /usr/local/share/alg-rgb-gui
    rm -f /usr/local/share/applications/alg-rgb-gui.desktop
    rm -f /usr/local/share/icons/hicolor/scalable/apps/alg-rgb-gui.svg
    rm -f /usr/local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png

    update-desktop-database /usr/local/share/applications 2>/dev/null || true
    gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor 2>/dev/null || true

    if [ -n "$SUDO_USER" ]; then
        USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        rm -f "${USER_HOME}/.local/share/applications/alg-rgb-gui.desktop"
        rm -f "${USER_HOME}/.local/share/icons/hicolor/scalable/apps/alg-rgb-gui.svg"
        rm -f "${USER_HOME}/.local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png"
        rm -f "${USER_HOME}/.config/autostart/alg-rgb-restore.desktop"
    fi
    echo "[+] System-wide GUI uninstalled."
else
    echo "[*] Removing Acer ALG RGB GUI for user (${USER})..."

    rm -f "${HOME}/.local/bin/alg-rgb-gui"
    rm -rf "${HOME}/.local/share/alg-rgb-gui"
    rm -f "${HOME}/.local/share/applications/alg-rgb-gui.desktop"
    rm -f "${HOME}/.local/share/icons/hicolor/scalable/apps/alg-rgb-gui.svg"
    rm -f "${HOME}/.local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png"
    rm -f "${HOME}/.config/autostart/alg-rgb-restore.desktop"

    update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
    gtk-update-icon-cache -q -t -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true

    echo "[+] User GUI uninstalled."
fi
