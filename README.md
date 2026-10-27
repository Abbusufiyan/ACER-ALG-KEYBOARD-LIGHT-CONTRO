# Acer ALG RGB Keyboard Controller & GUI

[![License: GPL-2.0](https://img.shields.io/badge/License-GPL%202.0-blue.svg)](LICENSE)
[![Platform: Arch Linux](https://img.shields.io/badge/Platform-Arch%20Linux-1793d1.svg)](https://archlinux.org)
[![Desktop: KDE Plasma 6](https://img.shields.io/badge/Desktop-KDE%20Plasma%206-1d99f3.svg)](https://kde.org/plasma-desktop/)
[![Framework: PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg)](https://riverbankcomputing.com/software/pyqt/)

A native Linux solution for controlling the built-in RGB keyboard backlight on **Acer ALG laptops** (such as the **Acer ALG AL15G-52** and **AL15G-53**).

Includes an in-tree Linux kernel driver, DKMS integration, a lightweight command-line utility, and a modern dark-themed **desktop GUI application** designed for Wayland and KDE Plasma 6.

---

## Architecture Overview

On Acer ALG series laptops, official keyboard RGB software is only distributed for Windows via an ACPI bridge (`AcpiBridge.sys`). On Linux, the keyboard backlight defaults to firmware static states without vendor support.

This project communicates directly with the firmware through the reverse-engineered **CLV0001 ACPI interface**:

```text
┌────────────────────────────────────────────────────────┐
│               Acer ALG RGB GUI                         │
│        (PyQt6 / Wayland / KDE Plasma 6)                │
└──────────────────────────┬─────────────────────────────┘
                           │ executes CLI / reads sysfs
                           ▼
┌────────────────────────────────────────────────────────┐
│                  alg-rgb CLI                           │
│        (Input validation, arg parsing, exit codes)     │
└──────────────────────────┬─────────────────────────────┘
                           │ writes validated payload
                           ▼
┌────────────────────────────────────────────────────────┐
│            Device Node: /dev/alg_rgb                   │
│        (Mode 0660, Group: alg-rgb, No Root Needed)     │
└──────────────────────────┬─────────────────────────────┘
                           │ character device file_operations
                           ▼
┌────────────────────────────────────────────────────────┐
│            alg_rgb Linux Kernel Driver                 │
│        (Evaluates _DSM UUID 93f224e4... Function 0x67) │
└──────────────────────────┬─────────────────────────────┘
                           │ ACPI evaluate DSM
                           ▼
┌────────────────────────────────────────────────────────┐
│            ACPI Device: \_SB.DCHU (CLV0001)            │
│        (Dispatches SCMD bytecode to EC Mailbox)        │
└──────────────────────────┬─────────────────────────────┘
                           │ ECMD write
                           ▼
┌────────────────────────────────────────────────────────┐
│         Hardware Embedded Controller (EC)              │
│  [C4 0D / C4 0E: Power] [C4 02: PWM] [CA 07/03: Color] │
└────────────────────────────────────────────────────────┘
```

---

## Features

### Desktop GUI (`alg-rgb-gui`)
- **Interactive Keyboard Glow Preview**: Stylized laptop keyboard rendering dynamic ambient light and keycap underglow matching the active RGB color and brightness.
- **16 Calibrated Color Presets**: One-click selection of all firmware-supported colors with hex codes.
- **Visual Color Picker & Hex Input**: Select arbitrary colors via visual dialog or hex (`#RRGGBB`). An integrated perceptual color-distance algorithm automatically selects the closest calibrated firmware preset.
- **Debounced Brightness Slider**: 5 discrete levels (`Off`, `25%`, `50%`, `75%`, `100%`) debounced to protect the ACPI/EC mailbox from rapid input spam.
- **Power Controls**: Single-click "Turn Off" button and "Turn On / Restore" functionality.
- **KDE Plasma 6 System Tray**: Taskbar icon dynamically tinted with the active keyboard color, featuring quick presets, brightness levels, and power toggles.
- **Live Diagnostics**: Non-intrusively monitors `/dev/alg_rgb` status, ACPI return status, and driver parameters without altering hardware state.
- **Optional Login Restore**: Optional autostart preference (`~/.config/autostart/alg-rgb-restore.desktop`) to reapply your preferred color and brightness on desktop login.

### Command-Line Interface (`alg-rgb`)
- Fast, dependency-free C binary for scripting and terminal usage.
- Strict input validation and descriptive error messages for unsupported firmware responses.
- Diagnostic inspection via `alg-rgb --diag`.

### Kernel Driver (`alg_rgb.ko`)
- Automatically registers `/dev/alg_rgb` character device with udev rules for group `alg-rgb`.
- Pure Function `0x67` implementation: does not issue unverified experimental ACPI calls.
- Strict ACPI return validation: distinguishes confirmed success (`0x67`), unsupported operations (`0x80000002`), and protocol errors.

---

## Supported Hardware & Environment

- **Laptop Models**:
  - Acer ALG AL15G-52 (Board: `Aspire Lite AL15G-52`) — *Verified*
  - Acer ALG AL15G-53 — *Verified*
- **ACPI Device**: `CLV0001` (`\_SB.DCHU`)
- **Operating System**: Arch Linux (Linux Kernel 6.x / 7.x)
- **Desktop Environment**: KDE Plasma 6 on Wayland (also works on X11 and other desktop environments)

---

## Supported Colors & Brightness

### Firmware Color Presets
The laptop embedded controller expects calibrated colors in internal `GRB` order:

| Name | Display Color | Hex Code | Firmware Payload (G R B Zone) |
| :--- | :---: | :---: | :--- |
| `red` | Red | `#FF0000` | `00 FF 00 F0` |
| `orange` | Orange | `#FF7F00` | `7F FF 00 F0` |
| `yellow` | Yellow | `#FFFF00` | `FF FF 00 F0` |
| `lime` | Lime | `#7FFF00` | `FF 7F 00 F0` |
| `light-green` | Light Green | `#3FFF00` | `FF 3F 00 F0` |
| `green` | Green | `#00FF00` | `FF 00 00 F0` |
| `green-cyan` | Green Cyan | `#00FF46` | `FF 00 46 F0` |
| `cyan` | Cyan | `#00FFC8` | `FF 00 C8 F0` |
| `light-blue` | Light Blue | `#007FC8` | `7F 00 C8 F0` |
| `blue` | Blue | `#0000C8` | `00 00 C8 F0` |
| `violet` | Violet | `#7F00C8` | `00 7F C8 F0` |
| `magenta` | Magenta | `#FF00C8` | `00 FF C8 F0` |
| `pink` | Pink | `#FF007F` | `00 FF 7F F0` |
| `flesh` | Flesh | `#FF7F3F` | `7F FF 3F F0` |
| `bluish-white` | Bluish White | `#3F7F7F` | `7F 3F 7F F0` |
| `white` | White | `#FFFFFF` | `FF FF FF F0` |
| `off` | Off | `#000000` | `00 00 00 40` (Power Rail Off) |

### Brightness Levels
- **0**: Off
- **1**: 25% (Low)
- **2**: 50% (Medium)
- **3**: 75% (High)
- **4**: 100% (Maximum)

---

## Prerequisites & Dependencies

On Arch Linux, ensure the base build tools, kernel headers, and Python PyQt6 packages are installed:

```bash
sudo pacman -S --needed base-devel linux-headers dkms python python-pyqt6
```

---

## Installation

### 1. Full System Installation (Driver + CLI + GUI)

Clone the repository and run the installer:

```bash
git clone https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO.git
cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
sudo ./install.sh
```

The installer will:
1. Verify the kernel module compiles cleanly against running headers before touching DKMS.
2. Build and install the `alg-rgb` CLI to `/usr/local/bin/alg-rgb`.
3. Create the `alg-rgb` system group and configure udev permissions (`0660`).
4. Register and install the `alg-rgb` DKMS kernel module.
5. Configure module auto-loading on boot (`/etc/modules-load.d/alg_rgb.conf`).
6. Install the GUI application, launcher binary, scalable icon, and desktop entry.

### 2. GUI-Only Installation (For Non-Root Updates)

If the driver and CLI are already installed, the GUI can be installed or updated for your user account without root:

```bash
cd gui
./install-gui.sh
```

---

## Launching the Application

### From KDE Plasma / Application Menu
Open Kickoff or KRunner (`Alt+Space`) and search for:
> **Acer ALG RGB**

### From the Terminal
Launch the GUI:
```bash
alg-rgb-gui
```

Launch directly minimized to the system tray:
```bash
alg-rgb-gui --minimized
```

### CLI Usage
```bash
# Set color at maximum brightness
alg-rgb red
alg-rgb cyan
alg-rgb white

# Set color with custom brightness (0-4)
alg-rgb blue 2
alg-rgb orange 3

# Turn off lighting
alg-rgb off

# Run diagnostics
alg-rgb --diag
```

---

## Uninstallation

To remove the complete driver, DKMS registration, CLI, and GUI:

```bash
cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
sudo ./uninstall.sh
```

To remove only the GUI desktop integration:

```bash
cd gui
./uninstall-gui.sh
```

---

## Verification & Automated Tests

Run the unit test suite to verify color algorithms, hex conversions, and diagnostic parsers:

```bash
python3 gui/tests/test_gui.py
```

Run CLI diagnostics:

```bash
alg-rgb --diag
```

Expected diagnostic output:

```text
[*] ACPI Namespace:
    CLV0001:00 (\_SB.DCHU): PRESENT (Status: 15)
[*] Kernel Driver & Device Node:
    Kernel Module:  alg_rgb is LOADED
    Device Node:    /dev/alg_rgb EXISTS
    Driver Diagnostic Data:
      driver_version: 0.1.3
      acpi_device: \_SB.DCHU (CLV0001)
      acpi_handle_bound: yes
      last_acpi_status: 0 (SUCCESS (firmware accepted last call))
      software_state: ON
```

---

## Troubleshooting

### 1. Permission Denied opening `/dev/alg_rgb`
Ensure your user account belongs to the `alg-rgb` group:
```bash
sudo usermod -aG alg-rgb $USER
```
Log out and log back in for group membership to take effect.

### 2. Device `/dev/alg_rgb` Does Not Exist
Check if the kernel module is loaded:
```bash
lsmod | grep alg_rgb
```
If not loaded, load it manually:
```bash
sudo modprobe alg_rgb
```

### 3. Check Kernel Diagnostic Logs
Inspect driver kernel log entries:
```bash
journalctl -k -b 0 | grep alg-rgb
```

---

## Hardware Safety & Limitations

- **ACPI Isolation**: This driver communicates only via ACPI `_DSM` Function `0x67`. Unknown experimental functions (such as `0x68`, `0x69`, `0x6A`) are intentionally not exposed to prevent hardware lockups.
- **Physical Output**: Software delivery of ACPI commands does not automatically guarantee physical LED output if physical keyboard wiring differs or if an EC hardware switch is triggered. Physical illumination must be confirmed visually.

---

## Contributing

Contributions, bug reports, and hardware compatibility testing on other Acer ALG models are welcome. Please open an issue or pull request with your `uname -r`, DMI board name (`cat /sys/class/dmi/id/board_name`), and diagnostic logs.

---

## License

This project is licensed under the **GNU General Public License v2.0** (GPL-2.0). See [LICENSE](LICENSE) for details.
