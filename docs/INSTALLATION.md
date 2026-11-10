# Installation & Setup Guide — Acer ALG Control Center

This document provides complete instructions for installing, configuring, and verifying the **Acer ALG Control Center** (RGB Keyboard & Dual Fan Control) on **Arch Linux** and compatible Linux distributions.

---

## Table of Contents
1. [Prerequisites & Dependencies](#prerequisites--dependencies)
2. [Automated System Installation](#automated-system-installation)
3. [User Permissions (`alg-rgb` Group)](#user-permissions-alg-rgb-group)
4. [DKMS Kernel Module Setup](#dkms-kernel-module-setup)
5. [Secure Boot Considerations](#secure-boot-considerations)
6. [GUI Desktop Integration & Autostart](#gui-desktop-integration--autostart)
7. [Post-Installation Verification](#post-installation-verification)
8. [Updating the Project](#updating-the-project)

---

## Prerequisites & Dependencies

### Arch Linux / Arch-based (EndeavourOS, Manjaro, CachyOS)
Install the required base build toolchain, running kernel headers, DKMS framework, and Python Qt6 runtime:

```bash
sudo pacman -S --needed base-devel linux-headers dkms python python-pyqt6
```

> [!NOTE]
> If you are using an alternative kernel (e.g., `linux-lts`, `linux-zen`, or `linux-hardened`), install the matching header package:
> ```bash
> sudo pacman -S --needed linux-lts-headers  # For LTS kernel
> sudo pacman -S --needed linux-zen-headers  # For Zen kernel
> ```

### Optional NVIDIA Telemetry Dependencies
To display live GPU utilization, temperature, power draw, and VRAM telemetry in the GUI:
```bash
sudo pacman -S --needed nvidia-utils  # Provides nvidia-smi
```

---

## Automated System Installation

The project includes an end-to-end installation script (`install.sh`) that automates kernel module compilation, DKMS registration, CLI binary deployment, udev permissions, and GUI registration.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO.git
   cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
   ```

2. **Run the installer with root privileges:**
   ```bash
   sudo ./install.sh
   ```

### What `install.sh` Does:
1. **Pre-flight Compile Test:** Verifies that both the CLI tools (`alg-rgb`, `alg-fan`) and the kernel module (`alg_rgb.ko`) compile cleanly against your running kernel headers before altering system directories.
2. **Binary Deployment:** Installs CLI binaries to `/usr/local/bin/alg-rgb` and `/usr/local/bin/alg-fan` with executable permissions (`0755`).
3. **Udev Rules Configuration:** Creates `/etc/udev/rules.d/99-alg-rgb.rules` granting group `alg-rgb` read/write access (`0660`) to `/dev/alg_rgb` and `/dev/alg_fan`.
4. **Group Creation & Assignment:** Creates the `alg-rgb` system group and adds your current user to it so you can run the GUI and CLI without `sudo`.
5. **DKMS Module Installation:** Copies source files to `/usr/src/alg-rgb-0.1.4`, builds the DKMS module, and installs it to `/extra`.
6. **Module Autoload on Boot:** Adds `alg_rgb` to `/etc/modules-load.d/alg_rgb.conf`.
7. **GUI Desktop Integration:** Installs the desktop launcher entry, scalable application icon, and application files.

---

## User Permissions (`alg-rgb` Group)

The udev rule restricts raw ACPI access to members of the `alg-rgb` group:
```text
KERNEL=="alg_*", SUBSYSTEM=="alg", GROUP="alg-rgb", MODE="0660"
```

To activate group membership for your current shell session without rebooting or logging out:
```bash
newgrp alg-rgb
```
Alternatively, log out and log back in to your desktop session (KDE Plasma, GNOME, etc.).

Verify that your user has proper group membership:
```bash
groups | grep alg-rgb
```

---

## DKMS Kernel Module Setup

The kernel module is managed via DKMS (Dynamic Kernel Module Support). Whenever your system updates its Linux kernel via `pacman -Syu`, DKMS automatically recompiles `alg_rgb.ko` for the new kernel version.

Verify DKMS status:
```bash
dkms status -m alg-rgb
```
Expected output:
```text
alg-rgb/0.1.4, 7.2.11-arch1-1, x86_64: installed
```

If you ever need to manually rebuild for the active kernel:
```bash
sudo dkms build -m alg-rgb -v 0.1.4
sudo dkms install -m alg-rgb -v 0.1.4
```

---

## Secure Boot Considerations

If Secure Boot is enabled in your laptop BIOS:
- The Linux kernel may enforce kernel module signature verification (`CONFIG_MODULE_SIG=y`).
- Unsigned DKMS modules will be blocked from loading with a `Required key not available` or `Operation not permitted` error.

### How to Sign the Module with MOK (Machine Owner Key):
1. Create a local MOK keypair (if not already present):
   ```bash
   sudo mokutil --generate-keypair
   ```
2. Enroll the key into your system UEFI MOK list:
   ```bash
   sudo mokutil --import /var/lib/shim-signed/mok/MOK.der
   ```
3. Reboot and complete key enrollment in the MOK blue screen menu.
4. Configure DKMS to sign modules automatically in `/etc/dkms/framework.conf`:
   ```text
   sign_tool="/usr/lib/modules/$(uname -r)/build/scripts/sign-file"
   sign_hash="sha256"
   mok_signing_key="/var/lib/shim-signed/mok/MOK.priv"
   mok_certificate="/var/lib/shim-signed/mok/MOK.der"
   ```

*(If Secure Boot is disabled in BIOS, module signing is not required.)*

---

## GUI Desktop Integration & Autostart

### Launching the Graphical Interface
- **From Application Menu:** Search for **"Acer ALG Control Center"** in your application launcher (KDE Kickoff, KRunner, GNOME Activities, Rofi, Waybar).
- **From Terminal:**
  ```bash
  alg-rgb-gui
  ```
- **From Terminal (Minimized to System Tray):**
  ```bash
  alg-rgb-gui --minimized
  ```

### Autostart on Desktop Login
You can configure keyboard lighting restoration and system tray monitoring on login:
1. Open **Acer ALG Control Center**.
2. Navigate to the **⚙️ Diagnostics & Settings** tab.
3. Check the box: **"Restore keyboard lighting automatically on desktop login"**.
4. Check the box: **"Minimize to system tray instead of exiting on window close"**.

---

## Post-Installation Verification

Run the built-in non-destructive diagnostic utilities to confirm proper driver binding:

### 1. Fan Controller Diagnostics
```bash
alg-fan --diag
```
Expected output:
```text
========================================
  Acer ALG Fan Driver Diagnostic Report 
========================================

[*] Hardware:
    Product Name:   Acer ALG AL15G-52
    Board Name:     Aspire Lite AL15G-52
    Kernel Version: 7.2.11-arch1-1 (x86_64)

[*] Kernel Driver & Device Node:
    Kernel Module:  alg_rgb is LOADED
    Device Node:    /dev/alg_fan EXISTS
    Fan Diagnostic Data:
      driver_version: 0.1.4
      acpi_device: \_SB.DCHU (CLV0001)
      acpi_handle_bound: yes
      last_acpi_status: 0 (SUCCESS)
      fan_mode: AUTO
========================================
```

### 2. RGB Backlight Diagnostics
```bash
alg-rgb -d
```
Expected output:
```text
========================================
  Acer ALG RGB Driver Diagnostic Report 
========================================
[*] ACPI Namespace:
    CLV0001:00 (\_SB.DCHU): PRESENT (Status: 15)
[*] Kernel Driver & Device Node:
    Kernel Module:  alg_rgb is LOADED
    Device Node:    /dev/alg_rgb EXISTS
    Driver Diagnostic Data:
      last_acpi_status: 0 (SUCCESS)
      software_state: ON
========================================
```

---

## Updating the Project

When a new version is released:
```bash
cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
git pull origin main
sudo ./install.sh
```
This cleanly updates the kernel DKMS module, replaces CLI binaries, and updates the PyQt6 GUI.
