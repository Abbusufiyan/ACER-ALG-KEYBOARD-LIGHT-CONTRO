#!/usr/bin/env bash

set -e

VERSION="0.1.4"
DKMS_NAME="alg-rgb"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/gui/uninstall-gui.sh" ]; then
    "${SCRIPT_DIR}/gui/uninstall-gui.sh"
fi

echo "[*] Unloading kernel module..."
sudo rmmod alg_rgb 2>/dev/null || true

echo "[*] Removing module autoload configuration..."
sudo rm -f /etc/modules-load.d/alg_rgb.conf

echo "[*] Removing udev rules..."
sudo rm -f /etc/udev/rules.d/99-alg-rgb.rules
sudo udevadm control --reload-rules 2>/dev/null || true

echo "[*] Removing CLI binaries..."
sudo rm -f /usr/local/bin/alg-rgb /usr/local/bin/alg-fan

echo "[*] Removing DKMS module for version ${VERSION}..."
sudo dkms remove -m ${DKMS_NAME} -v ${VERSION} --all 2>/dev/null || true

# Note: Stale 0.1.1 DKMS entry is preserved as requested.
# If cleanup is desired later, it can be removed with: sudo rm -rf /var/lib/dkms/alg-rgb/0.1.1

if [ -d "/usr/src/${DKMS_NAME}-${VERSION}" ]; then
    echo "[*] Removing DKMS source directory for version ${VERSION}..."
    sudo rm -rf "/usr/src/${DKMS_NAME}-${VERSION}"
fi

echo
echo "[+] Uninstallation complete"
