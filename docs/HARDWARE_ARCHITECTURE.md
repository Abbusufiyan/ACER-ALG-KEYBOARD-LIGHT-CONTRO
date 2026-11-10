# Hardware Architecture & ACPI Specification

This document details the reverse-engineered hardware architecture, ACPI contracts, Embedded Controller (EC) communication protocols, and kernel driver design for the **Acer ALG AL15G-52** and **AL15G-53** laptops.

---

## 1. Platform Identification & Baseboard Topology

| Hardware Attribute | Specification | Verification Source |
| :--- | :--- | :--- |
| **Laptop Family** | Acer ALG (Aspire Lite Gaming) | DMI `product_name` |
| **Model Numbers** | AL15G-52 / AL15G-53 | DMI `board_name` (`Aspire Lite AL15G-52`) |
| **Baseboard ODM** | Clevo ODM baseboard derivative | ACPI device IDs `CLV0001:00`, `CLV0002:00` |
| **CPU Architecture** | Intel Core i5-12450H (Alder Lake-P, 4P + 4E cores, 12 threads) | `/proc/cpuinfo` |
| **Discrete GPU** | NVIDIA GeForce RTX 2050 Mobile (GA107, 4GB GDDR6) | `lspci -vnn`, `nvidia-smi` |
| **BIOS Revision** | `1.07.01RAC2` (03/30/2024) | `/sys/class/dmi/id/bios_version` |
| **ACPI Device Path** | `\_SB.DCHU` (CLV0001:00) | Linux ACPI namespace tables |

---

## 2. ACPI `_DSM` Interface Specification

Under Windows, Acer provides a proprietary ACPI bridge driver (`AcpiBridge.sys`) that communicates with UEFI firmware via Device-Specific Methods (`_DSM`) located at ACPI device path `\_SB.DCHU`.

Under Linux, the `alg_rgb` kernel driver attaches to `\_SB.DCHU` and implements these standardized ACPI calls:

### ACPI UUID & Scope
* **ACPI Device Node:** `\_SB.DCHU` (CLV0001:00)
* **_DSM UUID:** `93f224e4-fbdc-4bbf-add6-db71bdc0afad`
* **Revision ID:** `0x00`

### DSDT Bytecode Routing:
In disassembled ACPI DSDT bytecode (`dsdt.dsl`):
```asl
Method (_DSM, 4, Serialized)
{
    If ((Arg0 == ToUUID ("93f224e4-fbdc-4bbf-add6-db71bdc0afad")))
    {
        Switch (Arg2)
        {
            Case (0x67) { Return (SCMD (Arg1, Arg2, Arg3)) } // Keyboard Backlight
            Case (0x68) { Return (SCMD (Arg1, Arg2, Arg3)) } // Manual Fan Speed
            Case (0x69) { Return (SCMD (Arg1, Arg2, Arg3)) } // Auto Fan Restore
        }
    }
    Return (0x80000002) // Unsupported
}
```

---

## 3. Keyboard RGB Subsystem (Function `0x67`)

### Color Buffer Encoding
Function `0x67` accepts a 4-byte buffer payload. Unlike standard RGB, the Embedded Controller expects values in **GRB (Green-Red-Blue)** byte ordering:

```text
Byte 0: Green component  (0x00 - 0xFF)
Byte 1: Red component    (0x00 - 0xFF)
Byte 2: Blue component   (0x00 - 0xFF)
Byte 3: Zone / Power byte (0xF0 = Zone Active / On, 0x40 = Power Rail Off)
```

### Color Mapping Table
| Color Preset | Hex Code | Payload (G R B Zone) | Description |
| :--- | :--- | :--- | :--- |
| `red` | `#FF0000` | `00 FF 00 F0` | Pure red |
| `orange` | `#FF7F00` | `7F FF 00 F0` | Amber orange |
| `yellow` | `#FFFF00` | `FF FF 00 F0` | Pure yellow |
| `lime` | `#7FFF00` | `FF 7F 00 F0` | Chartreuse / lime |
| `light-green`| `#3FFF00` | `FF 3F 00 F0` | Yellow green |
| `green` | `#00FF00` | `FF 00 00 F0` | Pure emerald green |
| `green-cyan` | `#00FF46` | `FF 00 46 F0` | Spring green |
| `cyan` | `#00FFC8` | `FF 00 C8 F0` | Turquoise / cyan |
| `light-blue` | `#007FC8` | `7F 00 C8 F0` | Sky blue |
| `blue` | `#0000C8` | `00 00 C8 F0` | Deep blue |
| `violet` | `#7F00C8` | `00 7F C8 F0` | Purple / violet |
| `magenta` | `#FF00C8` | `00 FF C8 F0` | Vivid magenta |
| `pink` | `#FF007F` | `00 FF 7F F0` | Hot pink |
| `flesh` | `#FF7F3F` | `7F FF 3F F0` | Warm flesh tone |
| `bluish-white`|`#3F7F7F` | `7F 3F 7F F0` | Cool white (6500K) |
| `white` | `#FFFFFF` | `FF FF FF F0` | Pure white (balanced) |
| `off` | `#000000` | `00 00 00 40` | Cuts power rail to LEDs |

### Brightness Scaling
Brightness (levels 0–4) is achieved by scaling the RGB channels proportionally while preserving color tone:
- Level 0: 0% (Power rail `0x40`)
- Level 1: 25% intensity
- Level 2: 50% intensity
- Level 3: 75% intensity
- Level 4: 100% full luminance

---

## 4. Dual Fan Control Subsystem (Functions `0x68` & `0x69`)

The laptop thermal dissipation layout consists of two independent blower fans:
1. **Fan 1 (CPU):** Cools the Intel Core i5-12450H CPU package.
2. **Fan 2 (GPU):** Cools the NVIDIA GeForce RTX 2050 Mobile GPU.

### Function `0x68`: Manual Duty Setting
Dispatches an ACPI Package containing a 4-byte buffer:
```text
Package {
    Buffer { cpu_raw_duty, gpu_raw_duty, 0x00, 0x00 }
}
```
* `cpu_raw_duty`: 8-bit unsigned integer (raw `64` to `255`, corresponding to 25%–100%).
* `gpu_raw_duty`: 8-bit unsigned integer (raw `64` to `255`, corresponding to 25%–100%).

In DSDT method `SCMD`:
```asl
If ((ToInteger (Arg1) == 0x68))
{
    If (^^PC00.LPCB.EC.ECOK)
    {
        Local4 = ARGS
        Local5 = Buffer (0x08) { 0x03, 0x00, 0xC1, 0x01, 0x00, 0x00, 0x00, 0x00 }
        Local5 [0x04] = (Local4 & 0xFF)         // Fan 1 (CPU) Duty
        ^^PC00.LPCB.EC.ECMD (Local5)

        Local5 = Buffer (0x08) { 0x03, 0x00, 0xC1, 0x02, 0x00, 0x00, 0x00, 0x00 }
        Local5 [0x04] = ((Local4 >> 0x08) & 0xFF) // Fan 2 (GPU) Duty
        ^^PC00.LPCB.EC.ECMD (Local5)
    }
}
```
Each fan's raw duty is written to Embedded Controller mailbox registers via EC command `0xC1` sub-registers `0x01` (CPU) and `0x02` (GPU).

### Function `0x69`: Automatic Closed-Loop Restore
Restores the laptop Embedded Controller to its default internal BIOS thermal governor:
```text
Package {
    Buffer { 0x03, 0x00, 0x00, 0x00 }
}
```
Bitmask `0x03` specifies both Fan 1 (`0x01`) and Fan 2 (`0x02`):
```asl
If ((ToInteger (Arg1) == 0x69))
{
    If (^^PC00.LPCB.EC.ECOK)
    {
        Local4 = ARGS
        If ((Local4 & One))  // Fan 1
        {
            ^^PC00.LPCB.EC.ECMD (Buffer (0x08) { 0x03, 0x00, 0xC1, 0xFF, 0x01, 0x00, 0x00, 0x00 })
        }
        If ((Local4 & 0x02)) // Fan 2
        {
            ^^PC00.LPCB.EC.ECMD (Buffer (0x08) { 0x03, 0x00, 0xC1, 0xFF, 0x02, 0x00, 0x00, 0x00 })
        }
    }
}
```
Command `0xC1:0xFF` instructs the EC firmware to re-enable autonomous closed-loop PID control according to BIOS thermal trip tables (`F1T1`–`F1T4`, `F2T1`–`F2T4`).

---

## 5. Hardware Safety Architecture & Boundaries

```text
┌────────────────────────────────────────────────────────┐
│            Silicon Hardware Protection                 │
│         Intel DTS PROCHOT (100°C)                      │
│         Hardware Clock Modulation / Thermal Throttling │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────┴─────────────────────────────┐
│          Firmware / ACPI Thermal Zone (TZ0)            │
│         _CRT Critical Temperature (120°C / 393.2 K)     │
│         Emergency Hardware Power Shutdown              │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────┴─────────────────────────────┐
│       Kernel Driver Floor Clamp (/dev/alg_fan)         │
│         Minimum Duty: 25% (raw byte 0x40 / 64)         │
│         Maximum Duty: 100% (raw byte 0xFF / 255)       │
│         Motor Stall & Overheating Prevention           │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────┴─────────────────────────────┐
│    Userspace Monitoring Engine (alg-rgb-gui)           │
│         Continuous 1s Sampling • 10s Rolling Windows   │
│         10s Rolling Average ≥ 80°C ──> 100% Cooling    │
│         Sustained Peak ≥ 85°C (≥3s) ──> 100% Cooling   │
│         Hysteresis Recovery: Avg < 75°C, Peak < 80°C   │
└────────────────────────────────────────────────────────┘
```

### Motor Stall Prevention
At duty cycles below 20%, brushless laptop fan motors risk insufficient starting torque, causing motor stall and rapid thermal escalation. The driver enforces a strict lower boundary:
```c
u8 cpu_raw = (u8)clamp((cpu_val * 255 + 50) / 100, 64, 255);
u8 gpu_raw = (u8)clamp((gpu_val * 255 + 50) / 100, 64, 255);
```
Neither the CLI nor the GUI can set duty below 25% (raw 64).

### Tachometer Pulse Limitation (Honest Hardware Reporting)
On the Acer ALG AL15G-52 chassis, standard tachometer pulse lines are connected directly to internal EC hardware counters and are **not** exposed to Linux `hwmon` or ACPI registers.
Because RPM numbers cannot be read legitimately without vendor flash ROM patches, this project intentionally reports `"Tachometer: N/A"` rather than generating fabricated RPM estimates.

---

## 6. Hardware Separation & Multi-Device Nodes

To eliminate race conditions and ACPI mailbox collisions, the kernel driver isolates lighting and cooling controls into separate character device interfaces:

| Device Node | Functionality | Permitted Payloads |
| :--- | :--- | :--- |
| `/dev/alg_rgb` | Keyboard Lighting | `<color_name>`, `<color_name> <brightness>`, `off` |
| `/dev/alg_fan` | Dual Fan Speeds | `auto`, `<pct>`, `<cpu_pct> <gpu_pct>`, `manual <cpu> <gpu>` |

Both device nodes are assigned major dynamic character device numbers with class `alg` and permissions `0660` owned by `root:alg-rgb`.
