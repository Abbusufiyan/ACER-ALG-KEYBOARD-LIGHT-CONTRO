# Dual Fan Control & Thermal Monitoring Guide

This guide explains how cooling management works on the **Acer ALG AL15G-52** and **AL15G-53**, covering command-line actuation, graphical profile tuning, dynamic thermal curves, and the automated spike-filter monitoring engine.

---

## Table of Contents
1. [Overview](#overview)
2. [CLI Utility (`alg-fan`)](#cli-utility-alg-fan)
3. [Graphical Fan Profiles](#graphical-fan-profiles)
4. [Custom Independent Tuning](#custom-independent-tuning)
5. [Smarter Thermal Monitoring Algorithm](#smarter-thermal-monitoring-algorithm)
6. [Hysteresis & Recovery Behavior](#hysteresis--recovery-behavior)
7. [Failsafe Guarantees](#failsafe-guarantees)

---

## Overview

Acer ALG laptops feature dual blower fans with dedicated heatpipe runs:
- **Fan 1 (CPU):** Cools the Intel Core i5-12450H CPU package.
- **Fan 2 (GPU):** Cools the NVIDIA GeForce RTX 2050 Mobile GPU.

The `alg-fan` driver communicates directly with the laptop Embedded Controller (EC) mailbox through ACPI methods:
* **SCMD `0x68` (Manual Duty):** Applies independent duty percentages (25%–100%) to Fan 1 and Fan 2.
* **SCMD `0x69` (Automatic Mode):** Releases manual control and restores the firmware's autonomous closed-loop thermal curves.

---

## CLI Utility (`alg-fan`)

The `alg-fan` utility (`/usr/local/bin/alg-fan`) allows direct terminal and script control.

### Basic Commands
```bash
# Restore firmware closed-loop automatic fan control
alg-fan auto

# Set both CPU and GPU fans to 50% duty
alg-fan 50

# Set independent speeds: Fan 1 (CPU) to 40%, Fan 2 (GPU) to 60%
alg-fan 40 60

# Inspect diagnostic status, active mode, and duty registers
alg-fan --diag
```

### Safety Rules Enforced by CLI:
- Minimum duty is automatically clamped to **25%** to prevent motor stalling.
- Maximum duty is clamped to **100%**.
- Invalid strings or out-of-range numbers are rejected with usage instructions.

---

## Graphical Fan Profiles

The **Thermals & Fans** tab in `alg-rgb-gui` provides 5 operational modes:

| Profile | Target Behavior | Typical Acoustic Level | Best For |
| :--- | :--- | :--- | :--- |
| ⚡ **Auto** | Firmware closed loop (`SCMD 0x69`) | Dynamic / variable | General daily use, web browsing |
| 🌙 **Silent** | Conservative low-RPM curve | Near-silent ($\le 35\text{ dBA}$) | Coding, reading, quiet environments |
| ⚖️ **Balanced** | Proportional dynamic curve | Moderate | Everyday multitasking, office work |
| 🚀 **Performance** | Aggressive high-cooling curve | Audible airflow | Gaming, compiling, rendering |
| 🛠️ **Custom** | Manual independent sliders | User-defined | Fixed benchmark loads, manual tuning |

### Dynamic Thermal Curves Table
Interpolation points for automated profiles (duty % vs. temperature °C):

```text
Silent Profile:
  45°C -> 25% | 55°C -> 30% | 65°C -> 42% | 75°C -> 55% | 85°C -> 75% | 92°C -> 100%

Balanced Profile:
  40°C -> 30% | 50°C -> 42% | 60°C -> 58% | 70°C -> 72% | 80°C -> 85% | 88°C -> 100%

Performance Profile:
  35°C -> 40% | 45°C -> 55% | 55°C -> 70% | 65°C -> 85% | 75°C -> 95% | 82°C -> 100%
```

---

## Custom Independent Tuning

In **Custom Mode**, you have independent manual control over each fan:
1. **CPU Fan Slider (25%–100%):** Controls Fan 1.
2. **GPU Fan Slider (25%–100%):** Controls Fan 2.
3. **🔗 Link CPU & GPU Fans Checkbox:**
   - **Checked (Default):** Moving either slider synchronizes both fans together.
   - **Unchecked:** Adjust Fan 1 and Fan 2 completely independently (e.g., higher GPU cooling for gaming without ramping CPU fan).
4. **Quick Duty Target Buttons:** Instantly sets targets to `Min (25%)`, `50%`, `75%`, or `Max (100%)`.

---

## Smarter Thermal Monitoring Algorithm

### The Problem with Naive Thresholds
Modern CPUs (like Intel Alder Lake-P) aggressively boost single cores during short bursts (launching apps, opening browser tabs). Temperatures can momentarily spike to 85°C+ for 500 ms before returning to 50°C.
Naive fan governors immediately blast fans to 100% on every momentary spike, creating disruptive noise oscillations.

### The 10-Second Rolling Average Engine
`alg-rgb-gui` implements a multi-sensor rolling window:
1. **Continuous 1-Second Sampling:** Telemetry polls all 15 system thermal sensors every 1,000 ms.
2. **Rolling 10-Second Deque:** Each sensor maintains a sliding history `deque([(timestamp, temp), ...])`. Samples older than 10 seconds are automatically evicted.
3. **Two-Tier Maximum Speed Trigger:**
   - **Tier 1 (Sustained Heat):** If any sensor's 10-second rolling average reaches **$\ge 80^\circ\text{C}$**, maximum fan speed (100%) engages immediately.
   - **Tier 2 (Sustained Peak Spike):** If a sensor crosses **$\ge 85^\circ\text{C}$**, a timer starts. 100% cooling is triggered **only** if the temperature remains at or above 85°C for at least **3 consecutive seconds**.
4. **Transient Spike Filter:** A 1-second spike to 87°C amidst a 55°C baseline produces a 10-second average of only 58.2°C, safely ignoring the burst without annoying fan ramp-ups.
5. **Instant Timer Reset:** As soon as peak temperatures fall below 85°C, the high-temperature timer resets to `None`. Any subsequent spike must begin a fresh 3-second measurement.

---

## Hysteresis & Recovery Behavior

To prevent rapid cycling ("fan hunting") when cooling down:
* **Hysteresis Band (5°C):** Once 100% cooling is engaged, it will **not** release until:
  1. All 10-second sensor rolling averages drop below **$75.0^\circ\text{C}$**.
  2. Peak instantaneous temperatures drop below **$80.0^\circ\text{C}$**.
* **Clean Mode Recovery:**
  - In **Auto Mode:** Automatically dispatches SCMD `0x69` to return fan control to the EC firmware governor.
  - In **Custom Mode:** Restores your configured custom slider percentages.
  - In **Preset Modes:** Re-evaluates and applies curve duty.
* **No Locked Fans:** The hardware registers are never left stuck at 100% manual duty once the thermal load resolves.

---

## Failsafe Guarantees

* **Firmware Safety Intact:** Hardware-level emergency protection (Intel CPU DTS `PROCHOT` at 100°C and ACPI `_CRT` thermal trip at 120°C) operates at the silicon/UEFI level and can never be overridden by userspace software.
* **Exit Cleanliness:** Closing the application, sending `SIGINT` / `SIGTERM`, or unloading the kernel module automatically restores the fans to firmware automatic mode (`SCMD 0x69`).
