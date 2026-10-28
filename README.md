# Acer ALG Control Center — RGB Keyboard & Dual Fan Control

[![License: GPL-2.0](https://img.shields.io/badge/License-GPL%202.0-blue.svg)](LICENSE)
[![Platform: Arch Linux](https://img.shields.io/badge/Platform-Arch%20Linux-1793d1.svg)](https://archlinux.org)
[![Desktop: KDE Plasma 6](https://img.shields.io/badge/Desktop-KDE%20Plasma%206-1d99f3.svg)](https://kde.org/plasma-desktop/)
[![Framework: PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Driver: DKMS](https://img.shields.io/badge/Kernel-DKMS%20v0.1.4-orange.svg)](dkms.conf)

A native Linux hardware utility and graphical control center designed specifically for **Acer ALG laptops** (such as the **Acer ALG AL15G-52** and **AL15G-53**).

Provides complete built-in RGB keyboard backlight control, genuine dual fan speed control (independent CPU Fan 1 & GPU Fan 2), dynamic thermal curves, real-time CPU & NVIDIA GPU telemetry, rolling temperature history graphing, and fail-safe firmware protection.

---

## Architecture Overview

On Acer ALG laptops, hardware management is traditionally locked to proprietary Windows software through vendor ACPI methods (`AcpiBridge.sys`). 

This project bridges hardware control under Linux using reverse-engineered, verified ACPI contracts and separate character device interfaces to prevent hardware command collisions:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Acer ALG Control Center                         │
│                    (PyQt6 / Wayland / KDE Plasma 6)                    │
└──────────────┬──────────────────────────┬──────────────────────────────┘
               │                          │
       [Keyboard RGB]             [Dual Fan Control]
               │                          │
               ▼                          ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│       alg-rgb CLI        │   │       alg-fan CLI        │
│ (/usr/local/bin/alg-rgb) │   │ (/usr/local/bin/alg-fan) │
└──────────────┬───────────┘   └──────────┬───────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│   Device: /dev/alg_rgb   │   │   Device: /dev/alg_fan   │
│ (Mode 0660, alg-rgb grp) │   │ (Mode 0660, alg-rgb grp) │
└──────────────┬───────────┘   └──────────┬───────────────┘
               │                          │
               │   ┌──────────────────────┴┐
               │   │                       │
               ▼   ▼                       ▼
┌─────────────────────────────────────────────────────────┐
│               alg_rgb Kernel Module (DKMS)              │
│       Function 0x67 (RGB)  │  Functions 0x68 & 0x69     │
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
               ▼                          ▼
┌─────────────────────────────────────────────────────────┐
│              ACPI Device: \_SB.DCHU (CLV0001:00)         │
│          UUID: 93f224e4-fbdc-4bbf-add6-db71bdc0afad     │
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│  EC Lighting Controller  │   │     EC Fan Mailbox       │
│  Backlight & Zone Colors │   │   Opcode 0xC1 Actuation  │
│  [C4 0D/0E/02, CA 07/03] │   │ [Fan 1: CPU, Fan 2: GPU] │
└──────────────────────────┘   └──────────────────────────┘
```

---

## Features

### ❄️ Dual Fan Speed Control & Cooling Management
- **5 Operational Profiles**:
  - ⚡ **Auto Mode**: Restores autonomous firmware closed-loop cooling (`SCMD 0x69`, payload `0x03`).
  - 🌙 **Silent Profile**: Quiet dynamic curve prioritizing low acoustics during light tasks.
  - ⚖️ **Balanced Profile**: Default adaptive curve balancing thermals and noise.
  - 🚀 **Performance Profile**: Aggressive cooling curve for gaming and heavy compilation.
  - 🛠️ **Custom Mode**: Fully adjustable manual sliders for independent CPU Fan 1 and GPU Fan 2.
- **Independent CPU & GPU Control**: Verified via DSDT bytecode — CPU Fan 1 (Byte 0) and GPU Fan 2 (Byte 1) are individually addressable in hardware.
- **🔗 Link CPU & GPU Fan Speeds**: Toggle sync locking to adjust both fans together or decouple them for custom independent tuning.
- **Quick Preset Buttons**: One-click duty targets: `Min (25%)`, `50%`, `75%`, `Max (100%)`.
- **Motor Stall Prevention**: Enforces a strict hardware safety floor of **minimum 25% duty** (raw byte `0x40`) in both the kernel driver and userspace.
- **Emergency Thermal Override**: Automatically engages 100% cooling priority if CPU DTS reaches $\ge 90^\circ\text{C}$ or NVIDIA GPU reaches $\ge 85^\circ\text{C}$.
- **Fail-Safe Cleanup**: Automatically restores firmware automatic mode on application close, force quit, or kernel module unload.

### ⌨️ Keyboard RGB Backlight Control
- **Interactive Keyboard Glow Preview**: Stylized laptop keyboard rendering dynamic ambient glow and keycap lighting matching the active RGB color and brightness.
- **16 Calibrated Color Presets**: One-click selection of all firmware-supported colors with hex codes.
- **Visual Color Picker & Hex Input**: Select arbitrary colors via visual dialog or hex (`#RRGGBB`). An integrated perceptual color-distance algorithm automatically selects the closest calibrated firmware preset.
- **Debounced Brightness Slider**: 5 discrete levels (`Off`, `25%`, `50%`, `75%`, `100%`) debounced to protect the ACPI/EC mailbox from rapid input spam.
- **Power Controls**: Single-click "Turn Off" button and "Turn On / Restore" functionality.
- **KDE Plasma 6 System Tray**: Taskbar icon dynamically tinted with the active keyboard color, featuring quick presets, brightness levels, and power toggles.

### 📊 Real-Time Telemetry & Monitoring
- **Real-Time CPU Core Thermals**: Individual tracking for Intel Alder Lake-P Package and all 8 performance/efficiency cores via kernel `coretemp`.
- **NVIDIA GeForce RTX 2050 Telemetry**: Live GPU core temperature, GPU utilization %, power draw (Watts), and VRAM allocation via `nvidia-smi`.
- **Storage & System Thermals**: Live monitoring of NVMe SSD temperature, ACPI motherboard thermal zone, and Wi-Fi module.
- **Live 60-Second Rolling Temperature Graph**: Continuous dual-curve plotting for both CPU and GPU against warning (85°C) and critical (100°C) thresholds.
- **Honest Hardware Reporting**: Standard Linux `hwmon` does not expose fan tachometer pulse channels on this chassis. The interface honestly reports `"Tachometer: N/A"` rather than displaying fabricated RPM numbers.

---

## Supported Hardware & Environment

- **Laptop Models**:
  - Acer ALG AL15G-52 (Board: `Aspire Lite AL15G-52`, BIOS `1.07.01RAC2`) — *Fully Verified*
  - Acer ALG AL15G-53 — *Supported*
- **ACPI Hardware ID**: `CLV0001:00` (`\_SB.DCHU`)
- **Processors**: Intel Core i5-12450H (Alder Lake-P) + NVIDIA GeForce RTX 2050 Mobile
- **Operating System**: Arch Linux (Kernel 6.x / 7.x)
- **Desktop Environment**: KDE Plasma 6 on Wayland (also works on X11 and other DEs)

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

## Installation

### Prerequisites (Arch Linux)
Ensure kernel headers and dependencies are installed:
```bash
sudo pacman -S --needed base-devel linux-headers dkms python python-pyqt6
```

### Full System Installation (Driver + CLI + GUI)
Clone the repository and run the installer:

```bash
git clone https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO.git
cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
sudo ./install.sh
```

The installer will:
1. Verify the kernel module compiles cleanly before touching DKMS.
2. Build and install both `alg-rgb` and `alg-fan` CLI utilities to `/usr/local/bin/`.
3. Create the `alg-rgb` system group and configure udev rules (`0660`) for `/dev/alg_*`.
4. Register and install the `alg-rgb` DKMS kernel module (version `0.1.4`).
5. Configure module auto-loading on boot (`/etc/modules-load.d/alg_rgb.conf`).
6. Register the desktop application, launcher binary, scalable icon, and menu entries.

### User GUI-Only Update
If the driver and CLI are already installed:
```bash
./gui/install-gui.sh
```

---

## Launching & Usage

### Launching the Graphical Interface
- **From Application Menu**: Search for **Acer ALG Control Center** in Kickoff / KRunner (`Alt+Space`).
- **From Terminal**:
  ```bash
  alg-rgb-gui
  ```
- **Launch Minimized to System Tray**:
  ```bash
  alg-rgb-gui --minimized
  ```

### CLI Fan Control (`alg-fan`)
```bash
# Restore firmware closed-loop automatic cooling
alg-fan auto

# Set both CPU and GPU fans to 50%
alg-fan 50

# Set independent speeds: CPU Fan 1 = 40%, GPU Fan 2 = 60%
alg-fan 40 60

# View fan diagnostic status
alg-fan --diag
```

### CLI Keyboard RGB Control (`alg-rgb`)
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

# View RGB diagnostic status
alg-rgb --diag
```

---

## Automated Tests & Verification

Run the test suite to verify curves, clamping, conversions, and file IO:
```bash
python3 -m unittest discover -s gui/tests
```

Expected output:
```text
Ran 21 tests in 0.282s
OK
```

---

## Uninstallation

To remove the kernel driver, DKMS module, CLI utilities, and desktop application:
```bash
cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
sudo ./uninstall.sh
```

---

## License

This project is licensed under the **GNU General Public License v2.0** (GPL-2.0). See [LICENSE](LICENSE) for details.
