# Demonstration Video Storyboard — Acer ALG Control Center

This storyboard outlines a concise, engaging 75-second demonstration video designed for YouTube, Reddit, Asciinema, and GitHub release notes showcasing the capabilities of the **Acer ALG Control Center**.

---

## Video Metadata
* **Target Duration:** 75 seconds
* **Resolution:** 1080p (1920x1080) / 60 FPS
* **Format:** MP4 (H.264) + Animated GIF excerpt for GitHub README
* **Music / Audio:** Modern lo-fi or subtle upbeat tech background music with clear narration / captions.

---

## Scene Breakdown

### Scene 1: The Problem (0:00 – 0:12)
* **Visual:**
  - Brief footage of the Acer ALG AL15G-52 laptop running Arch Linux.
  - Terminal showing default Arch Linux install: keyboard backlight is stuck on default red/off, fans ramp up loudly on every short spike.
  - Text overlay: *"Acer ALG Laptops on Linux: Proprietary Windows-only RGB & Fan controls... until now."*
* **Narration:**
  > "If you run Linux on an Acer ALG AL15G laptop, you know the frustration: keyboard backlight controls and fan management were locked inside Windows proprietary software. That changes today."

---

### Scene 2: Introducing Acer ALG Control Center (0:12 – 0:25)
* **Visual:**
  - Screen recording: Launching `alg-rgb-gui` from KDE Plasma 6 Kickoff.
  - The sleek Catppuccin / Breeze Dark window opens, displaying the animated vector keyboard preview with real-time glow.
  - Text overlay: *"Native Linux ACPI Bridge • DKMS Kernel Driver • PyQt6 & Wayland Native"*
* **Narration:**
  > "Meet Acer ALG Control Center: an open-source native Linux control suite powered by an in-tree ACPI driver and a modern PyQt6 interface designed for KDE Plasma and Wayland."

---

### Scene 3: Keyboard RGB Lighting Demo (0:25 – 0:42)
* **Visual:**
  - Cursor clicks through calibrated color swatches: Cyan, Violet, Emerald Green, Amber Orange.
  - Side-by-side PIP (picture-in-picture) showing the physical laptop keyboard changing colors in real-time.
  - Adjusting the brightness slider from 100% down to 25%, then clicking "Turn Off", and restoring with one click.
  - Opening the Visual Color Picker, selecting an arbitrary hex color, and watching the nearest-match algorithm map it instantly.
* **Narration:**
  > "Effortlessly control your 3-zone RGB keyboard with 16 calibrated firmware presets, smooth debounced brightness steps, and an intelligent perceptual color matcher."

---

### Scene 4: Dual Fan Control & Thermal Monitoring (0:42 – 1:02)
* **Visual:**
  - Transition to **Thermals & Fans** tab.
  - Pointing out live telemetry: CPU Package, individual core DTS thermals, NVIDIA RTX 2050 temperature, power draw in Watts, and rolling 60-second graph.
  - Unchecking "Link CPU & GPU Fans": independently adjusting CPU Fan 1 to 45% and GPU Fan 2 to 75%.
  - Highlighting the 10-second rolling average and spike-filtering algorithm: running a quick compilation task, showing CPU spike to 85°C for 1 second without fans unnecessarily blasting to 100%.
* **Narration:**
  > "Take command of dual cooling fans with independent CPU and GPU sliders. Our smart 10-second rolling average algorithm filters out brief temperature spikes, keeping your fans quiet while preserving hardware-level safety."

---

### Scene 5: CLI & System Tray Integration (1:02 – 1:12)
* **Visual:**
  - Minimizing to KDE Plasma 6 system tray: showing the dynamically tinted tray icon matching the keyboard color.
  - Terminal split-screen showing quick CLI execution:
    ```bash
    alg-rgb cyan 3
    alg-fan 50 70
    alg-fan auto
    ```
* **Narration:**
  > "Enjoy deep desktop integration with a color-matched system tray menu, plus full CLI utilities for scripting and terminal workflows."

---

### Scene 6: Open Source & Call to Action (1:12 – 1:15)
* **Visual:**
  - GitHub repository landing page: `https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO`
  - Badges: GPL-2.0, Arch Linux, DKMS, PyQt6.
  - One-line install command displayed: `sudo pacman -S --needed base-devel linux-headers dkms && sudo ./install.sh`
* **Narration:**
  > "100% free and open-source under GPL-2.0. Star the repository on GitHub and bring full hardware control to your Acer ALG today!"

---

## README GIF Creation Guide
To generate an animated preview GIF for the GitHub README from this video:
```bash
ffmpeg -ss 00:00:25 -to 00:00:45 -i demo_full.mp4 -vf "fps=15,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -loop 0 demo_preview.gif
```
