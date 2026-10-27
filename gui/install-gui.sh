#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -eq 0 ]; then
    echo "[*] Installing Acer ALG RGB GUI system-wide (/usr/local)..."

    # System-wide installation
    install -dm755 /usr/local/share/alg-rgb-gui
    cp -r "${SCRIPT_DIR}/alg_rgb_gui" /usr/local/share/alg-rgb-gui/
    cp -r "${SCRIPT_DIR}/assets" /usr/local/share/alg-rgb-gui/

    install -Dm755 "${SCRIPT_DIR}/alg-rgb-gui" /usr/local/bin/alg-rgb-gui

    install -Dm644 "${SCRIPT_DIR}/assets/alg-rgb-gui.svg" /usr/local/share/icons/hicolor/scalable/apps/alg-rgb-gui.svg
    install -Dm644 "${SCRIPT_DIR}/assets/alg-rgb-gui.png" /usr/local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png
    install -Dm644 "${SCRIPT_DIR}/assets/alg-rgb-gui.desktop" /usr/local/share/applications/alg-rgb-gui.desktop

    update-desktop-database /usr/local/share/applications 2>/dev/null || true
    gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor 2>/dev/null || true

    # Also install for sudo user if invoked via sudo
    if [ -n "$SUDO_USER" ]; then
        USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        mkdir -p "${USER_HOME}/.local/share/applications" "${USER_HOME}/.local/share/icons/hicolor/scalable/apps" "${USER_HOME}/.local/share/icons/hicolor/256x256/apps"
        install -Dm644 -o "$SUDO_USER" "${SCRIPT_DIR}/assets/alg-rgb-gui.desktop" "${USER_HOME}/.local/share/applications/alg-rgb-gui.desktop"
        install -Dm644 -o "$SUDO_USER" "${SCRIPT_DIR}/assets/alg-rgb-gui.svg" "${USER_HOME}/.local/share/icons/hicolor/scalable/apps/alg-rgb-gui.svg"
        install -Dm644 -o "$SUDO_USER" "${SCRIPT_DIR}/assets/alg-rgb-gui.png" "${USER_HOME}/.local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png"
    fi

    echo "[+] System-wide GUI installation complete."
    echo "    Binary: /usr/local/bin/alg-rgb-gui"
else
    echo "[*] Installing Acer ALG RGB GUI for current user (${USER})..."

    # User local installation (no root needed)
    mkdir -p "${HOME}/.local/bin"
    mkdir -p "${HOME}/.local/share/alg-rgb-gui"
    mkdir -p "${HOME}/.local/share/applications"
    mkdir -p "${HOME}/.local/share/icons/hicolor/scalable/apps"
    mkdir -p "${HOME}/.local/share/icons/hicolor/256x256/apps"

    cp -r "${SCRIPT_DIR}/alg_rgb_gui" "${HOME}/.local/share/alg-rgb-gui/"
    cp -r "${SCRIPT_DIR}/assets" "${HOME}/.local/share/alg-rgb-gui/"

    install -Dm755 "${SCRIPT_DIR}/alg-rgb-gui" "${HOME}/.local/bin/alg-rgb-gui"

    install -Dm644 "${SCRIPT_DIR}/assets/alg-rgb-gui.svg" "${HOME}/.local/share/icons/hicolor/scalable/apps/alg-rgb-gui.svg"
    install -Dm644 "${SCRIPT_DIR}/assets/alg-rgb-gui.png" "${HOME}/.local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png"
    install -Dm644 "${SCRIPT_DIR}/assets/alg-rgb-gui.desktop" "${HOME}/.local/share/applications/alg-rgb-gui.desktop"

    update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
    gtk-update-icon-cache -q -t -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true

    echo "[+] User GUI installation complete."
    echo "    Binary: ${HOME}/.local/bin/alg-rgb-gui"
    echo "    Desktop menu entry registered in KDE Plasma."
fi
