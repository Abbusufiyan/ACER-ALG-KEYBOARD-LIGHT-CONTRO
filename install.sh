#!/usr/bin/env bash

set -e

VERSION="0.1.4"
DKMS_NAME="alg-rgb"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Building CLI utilities (alg-rgb & alg-fan)..."
make -C "${SCRIPT_DIR}/cli"

echo "[*] Pre-flight: Verifying kernel module compiles cleanly before touching DKMS..."
make -C "${SCRIPT_DIR}/kernel"
make -C "${SCRIPT_DIR}/kernel" clean

echo "[*] Installing CLI utilities to /usr/local/bin..."
sudo install -Dm755 "${SCRIPT_DIR}/cli/alg-rgb" /usr/local/bin/alg-rgb
sudo install -Dm755 "${SCRIPT_DIR}/cli/alg-fan" /usr/local/bin/alg-fan

echo "[*] Setting up udev rules for RGB and Fan interfaces..."
sudo install -Dm644 -o root -g root /dev/null /etc/udev/rules.d/99-alg-rgb.rules 2>/dev/null || true
echo 'KERNEL=="alg_*", SUBSYSTEM=="alg", GROUP="alg-rgb", MODE="0660"' | sudo tee /etc/udev/rules.d/99-alg-rgb.rules >/dev/null

echo "[*] Ensuring alg-rgb group exists..."
getent group alg-rgb >/dev/null || sudo groupadd -r alg-rgb
if [ -n "$SUDO_USER" ]; then
    sudo usermod -aG alg-rgb "$SUDO_USER" || true
fi

# Note: Stale 0.1.1 DKMS entry is preserved as requested.
# If cleanup is desired later, it can be removed with: sudo rm -rf /var/lib/dkms/alg-rgb/0.1.1

echo "[*] Removing previous DKMS module version ${VERSION} (if installed)..."
sudo dkms remove -m ${DKMS_NAME} -v ${VERSION} --all 2>/dev/null || true
sudo rm -rf /usr/src/${DKMS_NAME}-${VERSION}
sudo mkdir -p /usr/src/${DKMS_NAME}-${VERSION}

echo "[*] Installing DKMS source for version ${VERSION}..."
sudo cp -r \
    "${SCRIPT_DIR}/cli" \
    "${SCRIPT_DIR}/kernel" \
    "${SCRIPT_DIR}/include" \
    "${SCRIPT_DIR}/dkms.conf" \
    "${SCRIPT_DIR}/LICENSE" \
    "${SCRIPT_DIR}/README.md" \
    /usr/src/${DKMS_NAME}-${VERSION}/

echo "[*] Registering DKMS module..."
sudo dkms add -m ${DKMS_NAME} -v ${VERSION}

echo "[*] Building DKMS module..."
sudo dkms build -m ${DKMS_NAME} -v ${VERSION}

echo "[*] Installing DKMS module..."
sudo dkms install -m ${DKMS_NAME} -v ${VERSION}

echo "[*] Configuring module autoload on boot..."
echo "alg_rgb" | sudo tee /etc/modules-load.d/alg_rgb.conf >/dev/null

echo "[*] Reloading udev rules..."
sudo udevadm control --reload-rules 2>/dev/null || true
sudo udevadm trigger --subsystem-match=alg 2>/dev/null || true

echo "[*] Reloading kernel module..."
sudo rmmod alg_rgb 2>/dev/null || true
sudo modprobe alg_rgb

if [ -f "${SCRIPT_DIR}/gui/install-gui.sh" ]; then
    "${SCRIPT_DIR}/gui/install-gui.sh"
fi

echo
echo "[+] Installation complete (alg-rgb v${VERSION})"
