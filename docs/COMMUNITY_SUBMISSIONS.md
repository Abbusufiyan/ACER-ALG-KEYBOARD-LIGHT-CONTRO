# Community Announcement & Outreach Drafts

> [!IMPORTANT]
> **Safety & Anti-Spam Notice:** Do not mass-post or automate submissions. Review each community's specific guidelines and post manually only with maintainer approval.

---

## 1. Reddit: `r/linux`

* **Target Flairs:** `Software`, `Project`, or `Release`
* **Timing:** Saturday/Sunday (Community Show & Tell / Weekend Showcase)

**Post Title:**
> [Project] Acer ALG Control Center: Native Linux ACPI driver & GUI for RGB keyboard and independent dual-fan control on Acer ALG laptops

**Post Body:**
```markdown
Hi everyone,

Like many users running Linux on modern white-label gaming laptops, I found that the **Acer ALG AL15G-52 / AL15G-53** laptops (Intel Core i5-12450H + NVIDIA RTX 2050 Mobile) had all keyboard RGB lighting and fan speed controls locked behind vendor Windows software (`AcpiBridge.sys`). Standard Linux tools like `acer-wmi` don't recognize the board, and `hwmon` doesn't expose PWM controls for this chassis.

Over the past few weeks, I reverse-engineered the ACPI DSDT bytecode and Embedded Controller (EC) mailboxes, implemented an in-tree DKMS Linux kernel driver, and built a native PyQt6 Control Center.

### What it does:
* **⌨️ Keyboard RGB Backlight:** 16 calibrated firmware presets, smooth debounced brightness scaling, hex color picker with perceptual nearest-matching, and a live vector keyboard glow preview.
* **❄️ Independent Dual-Fan Speed Control:** CPU Fan 1 and GPU Fan 2 are individually addressable in hardware via ACPI SCMD `0x68`. You can link them or tune them independently.
* **🧠 Smart 10-Second Rolling Average Monitoring:** Eliminates the annoying problem where a 500 ms CPU boost spike blasts fans to 100%. Continuous 1s sampling with a 10s rolling average and 85°C sustained-heat filter ensures quiet operation while keeping all silicon hardware protections (Intel PROCHOT 100°C) active.
* **📊 Deep System Telemetry:** Live core-by-core DTS tracking, NVIDIA GPU power/temp/VRAM telemetry, rolling 60s temperature graphs, and KDE Plasma 6 system tray integration.
* **⚙️ Dedicated CLI Tools:** Includes lightweight `alg-rgb` and `alg-fan` binaries for terminal and script workflows.

The project is 100% open-source under GPL-2.0 and packaged with DKMS for automatic kernel updates on Arch Linux.

* **GitHub Repository:** https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO
* **Screenshots & Documentation:** Available in the repo README!

Feedback, bug reports, and contributions from other Acer ALG owners are very welcome!
```

---

## 2. Reddit: `r/archlinux`

* **Target Flairs:** `Discussion` or `Software`

**Post Title:**
> Acer ALG AL15G-52 / AL15G-53: Native DKMS driver and PyQt6 GUI for RGB Keyboard & Dual Fan Control

**Post Body:**
```markdown
Hey Arch users,

If anyone here is daily-driving an **Acer ALG (AL15G-52 / AL15G-53)** laptop on Arch, you've probably noticed that out-of-the-box, the keyboard backlight stays stuck on default red/off and `sensors` / `fancontrol` doesn't expose PWM controls for the dual blowers.

I've written a dedicated kernel module (`alg_rgb.ko`) and desktop utility tailored for Arch Linux and KDE Plasma 6 on Wayland:

### Technical Details:
* ACPI Device: `\_SB.DCHU` (Hardware ID `CLV0001:00`, UUID `93f224e4-fbdc-4bbf-add6-db71bdc0afad`).
* Isolated Character Devices: `/dev/alg_rgb` (Function 0x67) and `/dev/alg_fan` (Functions 0x68 & 0x69) with udev rules (`0660`, `alg-rgb` group) so no `sudo` is needed.
* Dual Fan Actuation: Uses EC command `0xC1` to adjust Fan 1 (CPU) and Fan 2 (GPU) independently, with a hard 25% motor stall safety floor.
* Spike Filter: 10-second rolling window across all 15 hardware sensors to prevent transient 1-second boost spikes from causing loud fan ramp-ups.
* Full DKMS integration: Automatically rebuilds across `linux`, `linux-lts`, and `linux-zen` kernel upgrades.

### Quick Install (Arch):
```bash
sudo pacman -S --needed base-devel linux-headers dkms python python-pyqt6
git clone https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO.git
cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
sudo ./install.sh
```

GitHub Repo: https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO

I'm also preparing an AUR package (`alg-control-center-dkms-git`). If anyone is testing this on other kernels or desktop environments, please let me know your experience!
```

---

## 3. Reddit: `r/AcerOfficial` & `r/linuxhardware`

**Post Title:**
> Linux Hardware Support: Acer ALG AL15G-52 RGB Keyboard & Dual Fan Control Center (Open Source)

**Post Body:**
```markdown
Hi all,

For anyone looking to run Linux on the **Acer ALG AL15G-52 / AL15G-53** laptop family:

Under Windows, Acer relies on proprietary software for keyboard lighting and fan presets. Because the ALG series uses a Clevo-derivative white-label baseboard (`CLV0001:00`), standard Acer Linux drivers (`acer-wmi`) do not support it.

I've released **Acer ALG Control Center**, an open-source Linux suite that bridges these controls:
* Full RGB keyboard color changing (16 calibrated presets + arbitrary hex color picker) and 5 brightness levels.
* Genuine independent CPU and GPU fan speed control (Auto, Silent, Balanced, Performance, and Custom sliders).
* Thermal telemetry and rolling temperature graphing for CPU cores and NVIDIA RTX 2050 Mobile.
* Preserves all factory hardware protections and automatically restores firmware automatic mode on exit.

Source code, technical documentation, and installation scripts:
https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO
```

---

## 4. Arch Linux Forums / Hardware Thread Proposal

* **Category:** *GNU/Linux Hardware Support*
* **Topic Title:** `[Solved] Acer ALG AL15G-52 / AL15G-53 Keyboard RGB & Dual Fan Control (DKMS Driver)`

**Content Summary:**
Provides clean documentation of the laptop's DMI information (`Aspire Lite AL15G-52`), ACPI DSDT device node `\_SB.DCHU` (`CLV0001:00`), kernel module repository link, and diagnostic command outputs (`alg-fan --diag`, `alg-rgb -d`) to help future users searching the Arch Forums find a working solution.

---

## 5. Linux Hardware Database (`linux-hardware.org`) Submission

* **Action:** Run `hw-probe` on the laptop:
  ```bash
  sudo pacman -S --needed hw-probe
  sudo hw-probe -all -upload
  ```
* **Follow-up:** In the probe comments, submit a reference to `https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO` as the verified driver providing full RGB keyboard and dual-fan control support for DMI `Aspire Lite AL15G-52`.
