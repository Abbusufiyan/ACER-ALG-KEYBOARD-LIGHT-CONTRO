# Troubleshooting & Diagnostic Guide

This guide covers common issues, error codes, and step-by-step solutions when running the **Acer ALG Control Center** on Arch Linux and other distributions.

---

## Diagnostic Quick-Check

Before troubleshooting specific errors, run the non-destructive diagnostic tools:

```bash
# 1. Check fan driver & ACPI status
alg-fan --diag

# 2. Check RGB backlight driver & ACPI status
alg-rgb -d

# 3. Check kernel log messages from alg_rgb
sudo dmesg | grep -i alg
```

---

## 1. "Permission denied opening /dev/alg_fan" or "/dev/alg_rgb"

### Symptom:
Running `alg-rgb`, `alg-fan`, or launching `alg-rgb-gui` yields:
```text
Error: Permission denied opening /dev/alg_fan.
Ensure your user is in the 'alg-rgb' group.
```

### Cause:
The character device nodes `/dev/alg_rgb` and `/dev/alg_fan` are configured with permissions `0660` owned by `root:alg-rgb`. Your current user session is not recognized as a member of the `alg-rgb` system group.

### Solution:
1. Add your user to the group:
   ```bash
   sudo usermod -aG alg-rgb $USER
   ```
2. Activate the group in your current terminal session:
   ```bash
   newgrp alg-rgb
   ```
3. Or log out of your desktop session (KDE Plasma) and log back in.
4. Verify membership:
   ```bash
   groups | grep alg-rgb
   ```

---

## 2. "Device /dev/alg_fan does not exist"

### Symptom:
```text
Error: /dev/alg_fan does not exist.
Is the updated 'alg_rgb' module loaded?
```

### Cause:
The `alg_rgb` kernel module is not loaded into the active Linux kernel.

### Solution:
1. Check if the module is loaded:
   ```bash
   lsmod | grep alg_rgb
   ```
2. If not loaded, attempt manual insertion:
   ```bash
   sudo modprobe alg_rgb
   ```
3. Check `dmesg` for errors:
   ```bash
   sudo dmesg | tail -n 20
   ```
4. If `modprobe` reports `Module alg_rgb not found`, re-run the installer:
   ```bash
   cd ACER-ALG-KEYBOARD-LIGHT-CONTRO
   sudo ./install.sh
   ```

---

## 3. DKMS Build Fails After Kernel Upgrade

### Symptom:
After running `pacman -Syu` and rebooting into a new kernel, `/dev/alg_*` disappears, and `dkms status` shows an error.

### Cause:
Your running kernel version changed, but matching kernel headers were not installed, preventing DKMS from building `alg_rgb.ko`.

### Solution:
1. Verify your running kernel:
   ```bash
   uname -r
   ```
2. Install matching headers:
   ```bash
   # Standard kernel:
   sudo pacman -S --needed linux-headers

   # LTS kernel:
   sudo pacman -S --needed linux-lts-headers

   # Zen kernel:
   sudo pacman -S --needed linux-zen-headers
   ```
3. Trigger DKMS autoinstall:
   ```bash
   sudo dkms autoinstall
   ```
4. Reload the driver:
   ```bash
   sudo modprobe alg_rgb
   ```

---

## 4. Secure Boot Blocks Module Loading (`Key not available`)

### Symptom:
```text
modprobe: ERROR: could not insert 'alg_rgb': Key was rejected by service
```

### Cause:
UEFI Secure Boot is enabled, and the Linux kernel enforces module signature verification (`CONFIG_MODULE_SIG=y`).

### Solution:
- **Option A (Recommended):** Sign the module using Machine Owner Key (MOK) as detailed in [INSTALLATION.md](INSTALLATION.md#secure-boot-considerations).
- **Option B:** Disable Secure Boot in your laptop BIOS setup (accessible via `F2` at boot).

---

## 5. NVIDIA GPU Shows "Standby" in Telemetry

### Symptom:
In the GUI **Thermals & Fans** tab, the GPU card displays `"Standby"` and a fixed 20°C bar rather than live temperatures.

### Cause:
On hybrid graphics laptops (Intel Alder Lake-P + NVIDIA RTX 2050 Mobile), the NVIDIA discrete GPU automatically powers down to low-power RTD3 standby (`P8` state) when no 3D or CUDA applications are active. `nvidia-smi` cannot read temperatures from a sleeping GPU.

### Verification:
Run any application on the dedicated GPU (e.g. `prime-run glxgears` or `nvidia-smi`). As soon as the GPU wakes up, the GUI automatically resumes plotting live thermals, power draw, and VRAM utilization.

---

## 6. Emergency Recovery: Restoring Firmware Auto Fan Mode

If you ever wish to immediately reset the cooling fans back to full BIOS/EC automatic closed-loop control:

### Via CLI:
```bash
alg-fan auto
```

### Via Direct Device Node:
```bash
echo auto > /dev/alg_fan
```

### Via Module Reload:
Unloading the kernel module automatically triggers firmware auto restore in its exit handler:
```bash
sudo rmmod alg_rgb && sudo modprobe alg_rgb
```

---

## 7. Keyboard Backlight Does Not Illuminate Physically

### Symptom:
`alg-rgb` reports success, but the physical LEDs remain dark.

### Checklist:
1. Check brightness level:
   ```bash
   alg-rgb white 4
   ```
   (Level 0 or power-rail `0x40` turns LEDs off completely).
2. Check physical keyboard function keys (`Fn + F4` or `Fn + Space` depending on model) to ensure hardware backlight is not toggled off at the keyboard matrix layer.
3. Confirm ACPI hardware binding:
   ```bash
   alg-rgb -d
   ```
   Verify that `CLV0001:00 (\_SB.DCHU)` is marked `PRESENT (Status: 15)`.
