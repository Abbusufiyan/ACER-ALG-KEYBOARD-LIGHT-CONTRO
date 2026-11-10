# Keyboard RGB Backlight Control Guide

This guide covers keyboard lighting control on the **Acer ALG AL15G-52** and **AL15G-53**, including CLI syntax, GUI controls, the perceptual nearest-match color picker, and KDE Plasma 6 system tray integration.

---

## Table of Contents
1. [CLI Utility (`alg-rgb`)](#cli-utility-alg-rgb)
2. [16 Firmware Color Presets](#16-firmware-color-presets)
3. [Brightness Levels & Power Rail Control](#brightness-levels--power-rail-control)
4. [Visual Color Picker & Perceptual Color Matching](#visual-color-picker--perceptual-color-matching)
5. [Interactive Keyboard Glow Preview](#interactive-keyboard-glow-preview)
6. [KDE Plasma 6 System Tray Integration](#kde-plasma-6-system-tray-integration)
7. [Autostart Configuration](#autostart-configuration)

---

## CLI Utility (`alg-rgb`)

The `alg-rgb` utility (`/usr/local/bin/alg-rgb`) provides direct shell control over the keyboard backlight without launching the GUI.

### Commands
```bash
# Set color at maximum brightness (level 4)
alg-rgb red
alg-rgb cyan
alg-rgb white
alg-rgb violet

# Set color with custom brightness (0-4)
alg-rgb blue 2      # Blue at 50% brightness
alg-rgb orange 1    # Orange at 25% brightness
alg-rgb green 4     # Green at 100% brightness

# Turn off backlight completely (cuts power rail)
alg-rgb off

# Run hardware and ACPI diagnostics
alg-rgb -d
```

---

## 16 Firmware Color Presets

The Acer ALG Embedded Controller supports 16 hardware-calibrated color presets. The driver translates standard human color names and hex codes into internal `GRB` (Green-Red-Blue) bytecode:

| Preset Name | Color Preview | Hex Code | Firmware Bytecode (G R B Zone) |
| :--- | :---: | :---: | :--- |
| `red` | 🔴 Red | `#FF0000` | `00 FF 00 F0` |
| `orange` | 🟠 Orange | `#FF7F00` | `7F FF 00 F0` |
| `yellow` | 🟡 Yellow | `#FFFF00` | `FF FF 00 F0` |
| `lime` | 🟢 Lime | `#7FFF00` | `FF 7F 00 F0` |
| `light-green` | 🟢 Light Green | `#3FFF00` | `FF 3F 00 F0` |
| `green` | 🟢 Emerald Green | `#00FF00` | `FF 00 00 F0` |
| `green-cyan` | 🟢 Green Cyan | `#00FF46` | `FF 00 46 F0` |
| `cyan` | 🔵 Cyan / Aqua | `#00FFC8` | `FF 00 C8 F0` |
| `light-blue` | 🔵 Sky Blue | `#007FC8` | `7F 00 C8 F0` |
| `blue` | 🔵 Deep Blue | `#0000C8` | `00 00 C8 F0` |
| `violet` | 🟣 Violet | `#7F00C8` | `00 7F C8 F0` |
| `magenta` | 🟣 Magenta | `#FF00C8` | `00 FF C8 F0` |
| `pink` | 🌸 Pink | `#FF007F` | `00 FF 7F F0` |
| `flesh` | 🟤 Flesh / Peach | `#FF7F3F` | `7F FF 3F F0` |
| `bluish-white` | ⚪ Cool White | `#3F7F7F` | `7F 3F 7F F0` |
| `white` | ⚪ True White | `#FFFFFF` | `FF FF FF F0` |
| `off` | ⚫ Off | `#000000` | `00 00 00 40` (Power Cut) |

---

## Brightness Levels & Power Rail Control

The laptop hardware features 5 discrete brightness settings:

| Level | Percentage | Description | ACPI Payload Behavior |
| :---: | :---: | :--- | :--- |
| **0** | 0% | Backlight Off | Dispatches Zone byte `0x40` (cuts LED power rail completely) |
| **1** | 25% | Low Luminance | Preserves color tint; reduces channel intensity by 75% |
| **2** | 50% | Medium Luminance | Standard night-time productivity illumination |
| **3** | 75% | High Luminance | High daylight visibility |
| **4** | 100% | Maximum Luminance | Full LED drive strength |

### Hardware Debounce Safety
Rapid slider movement can flood the ACPI/EC mailbox with commands faster than the micro-controller can acknowledge them. `alg-rgb-gui` includes a **160 ms debounce timer** that coalesces slider events into a single clean ACPI call upon settling.

---

## Visual Color Picker & Perceptual Color Matching

The Acer ALG laptop firmware contains fixed LED look-up tables rather than an arbitrary 24-bit PWM generator. To support user customization through standard color dialogs:

1. **Standard Color Picker:** Click **"Open Visual Color Picker..."** or enter any hex code (e.g., `#E63946`).
2. **Perceptual Distance Algorithm:** `alg_rgb_gui.colors` computes Euclidean color distance in perceptual color space across all 16 calibrated firmware presets:
   $$\Delta E = \sqrt{2(R_1 - R_2)^2 + 4(G_1 - G_2)^2 + 3(B_1 - B_2)^2}$$
3. **Automatic Mapping:** The application maps your chosen color to the closest hardware preset and displays both the target hex code and active preset name.

---

## Interactive Keyboard Glow Preview

The top card of the **Keyboard RGB** tab renders a real-time vector representation of the 3-zone laptop keyboard:
* **Dynamic Keycap Illumination:** Keycaps and boundary glow dynamically shift in real-time to match your selected RGB hex color.
* **Luminance Scaling:** The rendered glow transparency scales with the active brightness slider (0% to 100%).
* **Applied Pill Indicator:** Displays `APPLIED` when hardware registers match the UI state.

---

## KDE Plasma 6 System Tray Integration

When `alg-rgb-gui` is running, it adds an icon to your KDE Plasma 6 system tray (or any Wayland/X11 system tray):
* **Dynamic Icon Tinting:** The tray icon SVG dynamically re-tints its color in real-time to reflect the keyboard's active color.
* **Right-Click Context Menu:**
  - Quick Color Presets (Red, Green, Blue, Cyan, Orange, Violet, White)
  - Quick Brightness Toggles (Off, 25%, 50%, 75%, 100%)
  - Power Toggle ("Turn Off" / "Turn On")
  - Open / Hide Window shortcut

---

## Autostart Configuration

To have your preferred color and brightness restored automatically on login:
1. In `alg-rgb-gui`, switch to the **⚙️ Diagnostics & Settings** tab.
2. Enable **"Restore keyboard lighting automatically on desktop login"**.
3. Enable **"Minimize to system tray instead of exiting on window close"**.
4. The application writes your preferences to `~/.config/alg-rgb/config.json` and creates `~/.config/autostart/alg-rgb-restore.desktop`.
