# Search Engine Optimization & Global Discoverability Plan

This document outlines the GitHub SEO, search ranking strategies, keyword metadata, and community backlink plan to make **Acer ALG Control Center** the #1 search result for Linux users seeking hardware control on Acer ALG laptops.

---

## 1. Search Intent & Keyword Strategy

### Primary Search Queries (High Intent)
| Keyword Phrase | Search Intent | Target Landing Page |
| :--- | :--- | :--- |
| `Acer ALG Linux fan control` | Fix loud fan or customize fan curves | Repository README & `FAN_CONTROL.md` |
| `Acer ALG keyboard light Linux` | Turn on / change keyboard RGB | Repository README & `RGB_KEYBOARD.md` |
| `Acer AL15G-52 Arch Linux` | General hardware support & setup | Repository README & `INSTALLATION.md` |
| `Aspire Lite AL15G-52 fan speed` | Independent fan tuning | `FAN_CONTROL.md` |
| `Acer ALG RGB keyboard Ubuntu Fedora` | Cross-distro installation | `INSTALLATION.md` |
| `CLV0001:00 Linux ACPI driver` | Technical ACPI identification | `HARDWARE_ARCHITECTURE.md` |

### Secondary Long-Tail Queries
* `Acer ALG AL15G-53 Linux compatibility`
* `Acer ALG fan loud spike fix Linux`
* `Acer ALG keyboard backlight stuck red`
* `Acer ALG control center Linux alternative`

---

## 2. GitHub Repository Optimization

### Recommended Repository Description (Max 350 Chars)
```text
Native Linux ACPI DKMS driver, CLI, and PyQt6 Control Center for Acer ALG laptops (AL15G-52 & AL15G-53). Features 16-color RGB keyboard backlight control, independent dual CPU/GPU fan speed tuning, smart 10s rolling-average thermal protection, and KDE Plasma 6 Wayland integration.
```

### GitHub Topics (Tags)
Configure these 15 high-ranking topics in your GitHub repository sidebar:
```text
acer-alg, acer-alg-linux, arch-linux, linux-fan-control, rgb-keyboard,
acer-laptop, kde-plasma, pyqt6, dkms, linux-hardware,
fan-control, acpi-driver, al15g-52, al15g-53, wayland
```

### Social Preview Card
Set the generated hero banner (`docs/screenshots/hero_preview.png`) as the official **Social Preview** image in your GitHub repository:
* Go to: **Settings** -> **General** -> **Social preview** -> **Edit** -> Upload `hero_preview.png`.

---

## 3. GitHub Pages Documentation Proposal

While GitHub's raw markdown viewer works well, hosting a dedicated, searchable documentation site on **GitHub Pages** dramatically improves Google Search indexing.

### Proposed Stack: MkDocs with Material Theme
1. **Configuration (`mkdocs.yml`):**
   ```yaml
   site_name: Acer ALG Control Center
   site_description: Documentation for Acer ALG Linux RGB & Fan Control Center
   site_url: https://abbusufiyan.github.io/ACER-ALG-KEYBOARD-LIGHT-CONTRO/
   repo_url: https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO
   theme:
     name: material
     palette:
       scheme: slate
       primary: light blue
       accent: cyan
     features:
       - navigation.tabs
       - navigation.sections
       - search.suggest
       - content.code.copy
   nav:
     - Home: index.md
     - Installation: INSTALLATION.md
     - Hardware Architecture: HARDWARE_ARCHITECTURE.md
     - Dual Fan Control: FAN_CONTROL.md
     - Keyboard RGB: RGB_KEYBOARD.md
     - Safety & Limitations: SAFETY_AND_LIMITATIONS.md
     - Troubleshooting: TROUBLESHOOTING.md
     - Uninstallation: UNINSTALLATION.md
   ```

2. **Automated GitHub Action (`.github/workflows/docs.yml`):**
   Automatically deploys the documentation to GitHub Pages on every push to `main`.

---

## 4. High-Authority Backlink Opportunities

Search engines heavily favor repositories referenced by authoritative domain names:

### 1. ArchWiki Laptop Section
* **Target Page:** `https://wiki.archlinux.org/title/Laptop/Acer`
* **Action:** Add a table row for **Acer ALG AL15G-52**:
  - Processor: Intel Core i5-12450H
  - GPU: NVIDIA RTX 2050 Mobile
  - Status: Working (Keyboard RGB and Dual Fans supported via `ACER-ALG-KEYBOARD-LIGHT-CONTRO`)

### 2. Arch User Repository (AUR)
Create and publish an official AUR package:
* Package Name: `alg-control-center-dkms-git`
* Upstream URL: `https://github.com/Abbusufiyan/ACER-ALG-KEYBOARD-LIGHT-CONTRO`
* The AUR page is permanently crawled by Google and indexed across all Arch Linux package search engines.

### 3. Linux Hardware Database (`linux-hardware.org`)
* Upload hardware probe using `sudo hw-probe -all -upload`.
* Link the probe to this GitHub repository as the verified third-party driver for DMI board `Aspire Lite AL15G-52`.

### 4. Open-Source Repositories & Lists
* Submit to `awesome-linux` / `awesome-hardware` GitHub collections.
* Create a listing on **AlternativeTo.net** as an open-source Linux alternative to Acer Care Center / NitroSense / PredatorSense.
