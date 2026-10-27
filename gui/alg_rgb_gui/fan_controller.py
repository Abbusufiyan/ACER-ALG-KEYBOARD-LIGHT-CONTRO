"""
Fan Control Engine and Hardware Dispatcher for Acer ALG AL15G-52.
==================================================================

Provides Windows Control Center-style fan management:
  - Automatic (firmware-managed closed loop)
  - Silent, Balanced, Performance (dynamic thermal curves)
  - Custom (independent manual CPU & GPU sliders)

Hardware Actuation Safety Gate:
  `hardware_writes_enabled = False` by default.
  Validates all contracts, inputs, and curves in Phase 2.
  Direct ACPI hardware writes remain gated until explicit user approval.
"""

import math
from enum import Enum
from typing import Dict, Any, List, Tuple, Optional


class FanMode(Enum):
    AUTO = "auto"
    SILENT = "silent"
    BALANCED = "balanced"
    PERFORMANCE = "performance"
    CUSTOM = "custom"


# Dynamic thermal curves: list of (temperature_c, duty_percentage)
# Points are linearly interpolated between thresholds.
SILENT_CURVE: List[Tuple[float, int]] = [
    (45.0, 25),
    (55.0, 30),
    (65.0, 42),
    (75.0, 55),
    (85.0, 75),
    (92.0, 100),
]

BALANCED_CURVE: List[Tuple[float, int]] = [
    (40.0, 30),
    (50.0, 42),
    (60.0, 58),
    (70.0, 72),
    (80.0, 85),
    (88.0, 100),
]

PERFORMANCE_CURVE: List[Tuple[float, int]] = [
    (35.0, 40),
    (45.0, 55),
    (55.0, 70),
    (65.0, 85),
    (75.0, 95),
    (82.0, 100),
]

# Hardware safety boundaries
MIN_SAFE_MANUAL_DUTY_PCT = 25  # Prevents fan motor stall / insufficient start torque
MAX_SAFE_MANUAL_DUTY_PCT = 100
EMERGENCY_TEMP_THRESHOLD_CPU = 90.0
EMERGENCY_TEMP_THRESHOLD_GPU = 85.0


def clamp_duty(pct: int) -> int:
    """Clamp duty percentage to safe operating bounds (25% to 100%)."""
    return max(MIN_SAFE_MANUAL_DUTY_PCT, min(MAX_SAFE_MANUAL_DUTY_PCT, int(pct)))


def pct_to_raw(pct: int) -> int:
    """Convert duty percentage (0-100) to 8-bit raw duty (0-255)."""
    clamped = max(0, min(100, pct))
    return int(round(clamped * 255.0 / 100.0))


def raw_to_pct(raw: int) -> int:
    """Convert 8-bit raw duty (0-255) to duty percentage (0-100)."""
    clamped = max(0, min(255, raw))
    return int(round(clamped * 100.0 / 255.0))


def interpolate_curve(curve: List[Tuple[float, int]], current_temp: float) -> int:
    """Linearly interpolate target duty percentage from a thermal curve."""
    if not curve:
        return 50

    if current_temp <= curve[0][0]:
        return curve[0][1]

    if current_temp >= curve[-1][0]:
        return curve[-1][1]

    for i in range(len(curve) - 1):
        t0, d0 = curve[i]
        t1, d1 = curve[i + 1]
        if t0 <= current_temp <= t1:
            ratio = (current_temp - t0) / (t1 - t0)
            return int(round(d0 + ratio * (d1 - d0)))

    return curve[-1][1]


class FanHardwareBackend:
    r"""
    ACPI Dispatcher Abstraction for Acer ALG AL15G-52.
    
    ACPI Contract (DSDT \_SB.DCHU._DSM UUID 93f224e4-fbdc-4bbf-add6-db71bdc0afad):
      - Function 0x68 (Manual Duty): Package { Buffer { duty1, duty2, 0, 0 } }
      - Function 0x69 (Auto Restore): Package { Buffer { bitmask, 0, 0, 0 } } (0x03 = both fans)
    """

    def __init__(self, hardware_writes_enabled: bool = False):
        self.hardware_writes_enabled = hardware_writes_enabled
        self.device_path = "/dev/alg_rgb"
        self.last_commanded_cpu_raw = 0
        self.last_commanded_gpu_raw = 0
        self.last_commanded_mode = "auto"
        self.call_history: List[Dict[str, Any]] = []

    def apply_manual_duty(self, cpu_pct: int, gpu_pct: int) -> Tuple[bool, str]:
        """Apply manual duty cycles to CPU Fan 1 and GPU Fan 2."""
        cpu_clamped = clamp_duty(cpu_pct)
        gpu_clamped = clamp_duty(gpu_pct)
        cpu_raw = pct_to_raw(cpu_clamped)
        gpu_raw = pct_to_raw(gpu_clamped)

        self.last_commanded_cpu_raw = cpu_raw
        self.last_commanded_gpu_raw = gpu_raw
        self.last_commanded_mode = "manual"

        event = {
            "action": "manual_duty",
            "cpu_pct": cpu_clamped,
            "gpu_pct": gpu_clamped,
            "cpu_raw": cpu_raw,
            "gpu_raw": gpu_raw,
            "hardware_dispatched": self.hardware_writes_enabled,
        }
        self.call_history.append(event)

        if not self.hardware_writes_enabled:
            return (
                True,
                f"Safety-Gated: Target validated (CPU: {cpu_clamped}%, GPU: {gpu_clamped}%). "
                f"Raw payload [{cpu_raw}, {gpu_raw}, 0, 0] ready for SCMD 0x68."
            )

        # Hardware execution path: blocked in Phase 2 until user approves Phase 3
        return (
            False,
            "Hardware writes disabled: Phase 3 kernel driver fan interface (SCMD 0x68/0x69) awaiting approval."
        )

    def apply_auto_mode(self) -> Tuple[bool, str]:
        """Restore autonomous firmware closed-loop control on both fans."""
        self.last_commanded_mode = "auto"
        event = {
            "action": "auto_restore",
            "hardware_dispatched": self.hardware_writes_enabled,
        }
        self.call_history.append(event)

        if not self.hardware_writes_enabled:
            return True, "Safety-Gated: Firmware Automatic mode active (EC closed loop). Payload [0x03, 0, 0, 0] ready for SCMD 0x69."

        return (
            False,
            "Hardware writes disabled: Phase 3 kernel driver fan interface (SCMD 0x68/0x69) awaiting approval."
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "hardware_writes_enabled": self.hardware_writes_enabled,
            "last_mode": self.last_commanded_mode,
            "last_cpu_raw": self.last_commanded_cpu_raw,
            "last_gpu_raw": self.last_commanded_gpu_raw,
            "total_calls": len(self.call_history),
        }


class FanControllerEngine:
    """
    High-level fan controller engine managing modes, curves, and thermal updates.
    """

    def __init__(self, backend: Optional[FanHardwareBackend] = None):
        self.backend = backend or FanHardwareBackend(hardware_writes_enabled=False)
        self.current_mode = FanMode.AUTO
        self.custom_cpu_duty = 50
        self.custom_gpu_duty = 50
        self.sync_fans = True

        self.active_cpu_target_pct = 50
        self.active_gpu_target_pct = 50
        self.emergency_override = False
        self.last_status_message = "Firmware Automatic (EC Closed-Loop Active)"

    def set_sync_fans(self, sync: bool):
        """Enable or disable synchronizing CPU and GPU fan speeds."""
        self.sync_fans = sync
        if self.sync_fans:
            self.custom_gpu_duty = self.custom_cpu_duty
            if self.current_mode == FanMode.CUSTOM:
                self.apply_custom_duty()

    def set_mode(self, mode: FanMode) -> Tuple[bool, str]:
        """Switch operational fan mode."""
        self.current_mode = mode
        if mode == FanMode.AUTO:
            self.emergency_override = False
            ok, msg = self.backend.apply_auto_mode()
            self.last_status_message = msg
            return ok, msg
        elif mode == FanMode.CUSTOM:
            return self.apply_custom_duty()
        else:
            # Presets: Silent, Balanced, Performance
            # Apply initial duty based on default baseline
            return self.update_preset_duty(45.0, 40.0)

    def set_custom_duty(self, fan_id: int, duty_pct: int) -> Tuple[bool, str]:
        """Update duty for Fan 1 (CPU) or Fan 2 (GPU) in Custom mode."""
        clamped = clamp_duty(duty_pct)
        if fan_id == 1:
            self.custom_cpu_duty = clamped
            if self.sync_fans:
                self.custom_gpu_duty = clamped
        elif fan_id == 2:
            self.custom_gpu_duty = clamped
            if self.sync_fans:
                self.custom_cpu_duty = clamped

        if self.current_mode == FanMode.CUSTOM:
            return self.apply_custom_duty()
        return True, f"Stored custom target: {clamped}%"

    def apply_custom_duty(self) -> Tuple[bool, str]:
        """Dispatch current custom sliders to backend."""
        self.active_cpu_target_pct = self.custom_cpu_duty
        self.active_gpu_target_pct = self.custom_gpu_duty
        ok, msg = self.backend.apply_manual_duty(self.custom_cpu_duty, self.custom_gpu_duty)
        self.last_status_message = msg
        return ok, msg

    def update_preset_duty(self, cpu_temp: float, gpu_temp: float) -> Tuple[bool, str]:
        """Interpolate duty from the active curve based on current temperatures."""
        hottest = max(cpu_temp, gpu_temp)

        if self.current_mode == FanMode.SILENT:
            target = interpolate_curve(SILENT_CURVE, hottest)
        elif self.current_mode == FanMode.BALANCED:
            target = interpolate_curve(BALANCED_CURVE, hottest)
        elif self.current_mode == FanMode.PERFORMANCE:
            target = interpolate_curve(PERFORMANCE_CURVE, hottest)
        else:
            target = 50

        self.active_cpu_target_pct = target
        self.active_gpu_target_pct = target
        ok, msg = self.backend.apply_manual_duty(target, target)
        self.last_status_message = f"Profile [{self.current_mode.value.upper()}]: {target}% target at {hottest:.0f}°C"
        return ok, msg

    def tick_thermal_update(self, cpu_temp: float, gpu_temp: float) -> Dict[str, Any]:
        """Periodic thermal update tick called on sensor poll (1-2s interval)."""
        # 1. Emergency Safety Floor Check
        if cpu_temp >= EMERGENCY_TEMP_THRESHOLD_CPU or gpu_temp >= EMERGENCY_TEMP_THRESHOLD_GPU:
            self.emergency_override = True
            # Revert to full auto firmware protection or max cooling
            self.backend.apply_manual_duty(100, 100)
            self.active_cpu_target_pct = 100
            self.active_gpu_target_pct = 100
            self.last_status_message = (
                f"⚠️ EMERGENCY THERMAL SAFETY: CPU={cpu_temp:.0f}°C, GPU={gpu_temp:.0f}°C. "
                "Forced 100% cooling to protect hardware."
            )
            return self.get_state_snapshot()

        if self.emergency_override and (cpu_temp < 75.0 and gpu_temp < 70.0):
            self.emergency_override = False

        # 2. Normal Mode Processing
        if self.current_mode == FanMode.AUTO:
            self.active_cpu_target_pct = 0
            self.active_gpu_target_pct = 0
            self.last_status_message = "Firmware Automatic (EC Closed-Loop Active)"
        elif self.current_mode in (FanMode.SILENT, FanMode.BALANCED, FanMode.PERFORMANCE):
            self.update_preset_duty(cpu_temp, gpu_temp)
        elif self.current_mode == FanMode.CUSTOM:
            self.active_cpu_target_pct = self.custom_cpu_duty
            self.active_gpu_target_pct = self.custom_gpu_duty

        return self.get_state_snapshot()

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Return snapshot of current fan controller state for UI display."""
        return {
            "mode": self.current_mode.value,
            "sync_fans": self.sync_fans,
            "custom_cpu_duty": self.custom_cpu_duty,
            "custom_gpu_duty": self.custom_gpu_duty,
            "active_cpu_pct": self.active_cpu_target_pct,
            "active_gpu_pct": self.active_gpu_target_pct,
            "active_cpu_raw": pct_to_raw(self.active_cpu_target_pct),
            "active_gpu_raw": pct_to_raw(self.active_gpu_target_pct),
            "emergency_override": self.emergency_override,
            "status_message": self.last_status_message,
            "hardware_writes_enabled": self.backend.hardware_writes_enabled,
        }
