# Uninstallation Guide — Acer ALG Control Center

This document explains how to cleanly and completely remove the **Acer ALG Control Center** (kernel driver, DKMS module, CLI utilities, and desktop GUI) from your system.

---

## Automated Uninstallation (Recommended)

1. Open a terminal and navigate to your cloned repository directory:
   ```bash
   cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
   ```

2. Run the automated uninstaller:
   ```bash
   sudo ./uninstall.sh
   ```

### What `uninstall.sh` Removes:
* **Failsafe Restoration:** Sends ACPI command `0x69` to restore fans to autonomous firmware automatic closed loop before unloading.
* **Kernel Module:** Unloads `alg_rgb.ko` via `rmmod`.
* **Autoload Configuration:** Deletes `/etc/modules-load.d/alg_rgb.conf`.
* **Udev Rules:** Deletes `/etc/udev/rules.d/99-alg-rgb.rules` and reloads udev rules.
* **CLI Utilities:** Deletes `/usr/local/bin/alg-rgb` and `/usr/local/bin/alg-fan`.
* **DKMS Registration:** Completely deregisters and deletes `alg-rgb/0.1.4` from the DKMS tree and removes `/usr/src/alg-rgb-0.1.4`.
* **Desktop Application:** Removes desktop launcher entries (`alg-rgb-gui.desktop`), icons (SVG & 256x256 PNG), and binary wrappers.

---

## Manual Step-by-Step Cleanup (Alternative)

If you have already deleted the repository folder, you can run the following commands manually:

### 1. Unload Driver & Clean Kernel Autoload
```bash
sudo rmmod alg_rgb 2>/dev/null || true
sudo rm -f /etc/modules-load.d/alg_rgb.conf
```

### 2. Remove DKMS Registration
```bash
sudo dkms remove -m alg-rgb -v 0.1.4 --all 2>/dev/null || true
sudo rm -rf /usr/src/alg-rgb-0.1.4
```

### 3. Remove Udev Rules & CLI Binaries
```bash
sudo rm -f /etc/udev/rules.d/99-alg-rgb.rules
sudo udevadm control --reload-rules
sudo rm -f /usr/local/bin/alg-rgb /usr/local/bin/alg-fan
```

### 4. Remove Desktop Application & Icons
```bash
# System-wide files:
sudo rm -f /usr/local/bin/alg-rgb-gui
sudo rm -rf /usr/local/share/alg-rgb-gui
sudo rm -f /usr/local/share/applications/alg-rgb-gui.desktop
sudo rm -f /usr/local/share/icons/hicolor/scalable/apps/alg-rgb-gui.svg
sudo rm -f /usr/local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png

# User local files:
rm -f ~/.local/bin/alg-rgb-gui
rm -rf ~/.local/share/alg-rgb-gui
rm -f ~/.local/share/applications/alg-rgb-gui.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/alg-rgb-gui.svg
rm -f ~/.local/share/icons/hicolor/256x256/apps/alg-rgb-gui.png
rm -f ~/.config/autostart/alg-rgb-restore.desktop

# Update system caches:
update-desktop-database ~/.local/share/applications 2>/dev/null || true
gtk-update-icon-cache -q -t -f ~/.local/share/icons/hicolor 2>/dev/null || true
```

### 5. Remove User Configuration & System Group (Optional)
```bash
# Remove saved user profile (last color, fan presets):
rm -rf ~/.config/alg-rgb

# Remove alg-rgb group (if no other users need it):
sudo groupdel alg-rgb 2>/dev/null || true
```

---

## Verification

Confirm that no lingering files or modules remain:
```bash
# Verify kernel module is gone:
lsmod | grep alg_rgb

# Verify DKMS tree is clean:
dkms status -m alg-rgb

# Verify binaries are removed:
which alg-rgb alg-fan alg-rgb-gui
```
All commands should return empty / not found.
