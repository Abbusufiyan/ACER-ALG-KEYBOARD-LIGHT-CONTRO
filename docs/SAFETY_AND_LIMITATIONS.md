# Hardware Safety Guarantees & Technical Limitations

Safety is the paramount design consideration of the **Acer ALG Control Center**. When dealing with laptop thermal dissipation and low-level Embedded Controller registers, software bugs or reckless overrides can cause hardware damage.

This document describes the multi-tiered safety architecture, hardware protections that remain permanently enabled, and technical limitations of the Acer ALG platform.

---

## 1. Multi-Tiered Safety Architecture

```text
Level 1: CPU Silicon Hardware Throttle (PROCHOT at 100°C)
   │  └── Pure hardware modulation: automatically drops clock multipliers
   │
Level 2: ACPI Thermal Zone Critical Shutdown (_CRT at 120°C)
   │  └── Firmware protection: power delivery cut to prevent physical damage
   │
Level 3: Kernel Driver Floor Clamp (25% Duty / Raw 64)
   │  └── Prevents fan motor stall, back-EMF, and zero-RPM heat buildup
   │
Level 4: Userspace Dual-Trigger Monitoring Engine
   │  └── 10s rolling average ≥ 80°C or sustained peak ≥ 85°C (≥3s) engages 100% cooling
   │
Level 5: Fail-Safe Exit & Crash Recovery
      └── Automatically restores firmware closed loop (SCMD 0x69) on exit/kill/unload
```

---

## 2. Inviolable Hardware Protections

The software communicates exclusively through standard ACPI Device-Specific Methods (`_DSM` on `\_SB.DCHU`). It **does not** perform direct raw port I/O (`inb`/`outb`) to arbitrary EC registers.

* **Intel CPU Hardware Thermal Protection (PROCHOT):**
  The Intel Core i5-12450H DTS (Digital Thermal Sensor) continuously monitors die temperatures. If temperature reaches **100°C**, the processor engages hardware clock throttling and voltage reduction directly in silicon.
  *Userspace software and ACPI drivers cannot disable, delay, or override PROCHOT.*
* **ACPI Critical Trip Point (`_CRT`):**
  Disassembled DSDT bytecode defines the critical thermal trip at `0x0F5C` (393.2 Kelvin / **120°C**). If thermals ever reach this threshold, the motherboard hardware cut-off immediately turns off power to protect VRMs and silicon.
* **Firmware Automatic Fallback:**
  Whenever manual duty is disengaged, the Embedded Controller resumes autonomous closed-loop PID regulation using internal BIOS trip tables (`F1T1`–`F1T4`, `F2T1`–`F2T4`).

---

## 3. Motor Stall Prevention (25% Duty Floor)

Brushless laptop fans require a minimum starting voltage to overcome static friction and inertia. If commanded below approximately 20% duty, the fan blades stop spinning while power continues flowing through the motor windings, causing heat accumulation and potential coil burnout.

Both the kernel driver (`alg_rgb.c`) and userspace controller (`fan_controller.py`) enforce a hard floor:
```c
/* Clamp between 25% (raw 64) and 100% (raw 255) */
cpu_raw = (u8)clamp((cpu_val * 255 + 50) / 100, 64, 255);
gpu_raw = (u8)clamp((gpu_val * 255 + 50) / 100, 64, 255);
```
No CLI command or GUI slider can request less than 25% duty.

---

## 4. Hardware Limitations (Honest Technical Reporting)

### 1. Tachometer Pulse Readings (No Fabricated RPMs)
* **Status:** `Tachometer: N/A`
* **Technical Reason:** Standard laptop tachometer pulse lines on this chassis are wired internally to EC micro-controller counter pins and are **not** routed to standard `hwmon` PWM/tachometer interfaces or ACPI reporting methods.
* **Our Policy:** Other third-party utilities often display synthetic RPM calculations (e.g. multiplying duty percentage by 5000 RPM). This project strictly refuses to fabricate RPM figures, reporting `"Tachometer: N/A"` honestly while accurately displaying actual ACPI commanded duty cycles.

### 2. Discrete RGB Lighting Zones
* **Status:** Single-zone global lighting
* **Technical Reason:** While the keyboard membrane contains 3 physical LED distribution segments, the hardware EC rail controls all 3 zones in unison (Function `0x67` uses broadcast zone byte `0xF0`). Per-key addressable RGB is not supported by the physical motherboard.

### 3. Suspended & Sleep Transitions
* Upon system sleep (`S3` or `s2idle`), the Embedded Controller temporarily resets fan duty registers to default automatic operation.
* When the laptop resumes, `alg-rgb-gui` detects the wake event and re-applies your preferred profile within its next 1-second telemetry cycle.

---

## 5. Supported Hardware vs. Non-Compatible Models

| Laptop Model | Motherboard Board Name | BIOS ID | Support Status |
| :--- | :--- | :--- | :--- |
| **Acer ALG AL15G-52** | `Aspire Lite AL15G-52` | `1.07.01RAC2` | **Fully Verified & Tested** |
| **Acer ALG AL15G-53** | `Aspire Lite AL15G-53` | Similar RAC series | **Supported (Identical EC/ACPI)** |
| **Acer Nitro 5 / 16 / 17** | Various Nitro boards | InsydeH2O | **Incompatible** (Uses `acer-wmi` / PredatorSense EC) |
| **Acer Predator Helios** | Various Predator boards | InsydeH2O | **Incompatible** (Uses PredatorSense Gaming WMI) |
| **Acer Swift / Aspire 3/5** | Various Aspire boards | Generic Acer | **Incompatible** (No `CLV0001` ACPI device) |

> [!CAUTION]
> Do not attempt to force-load this driver on non-ALG Acer laptops. Other Acer models use different ACPI GUIDs and proprietary WMI methods (`acer-wmi`). The `alg_rgb` driver checks for the presence of ACPI handle `\_SB.DCHU` (`CLV0001:00`) before binding.
