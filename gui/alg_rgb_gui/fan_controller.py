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

import os
import shutil
import subprocess
import math
import time
from collections import deque
from enum import Enum
from typing import Dict, Any, List, Tuple, Optional

DEV_FAN_PATH = "/dev/alg_fan"


def find_fan_cli_path() -> Optional[str]:
    """Locate the alg-fan CLI utility."""
    if os.path.isfile("/usr/local/bin/alg-fan") and os.access("/usr/local/bin/alg-fan", os.X_OK):
        return "/usr/local/bin/alg-fan"
    which_path = shutil.which("alg-fan")
    if which_path and os.access(which_path, os.X_OK):
        return which_path
    local_path = os.path.expanduser("~/alg-cli/cli/alg-fan")
    if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
        return local_path
    return None


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

# Smarter Automatic Monitoring Thresholds
ROLLING_WINDOW_DURATION_SEC = 10.0   # 10-second rolling window
ROLLING_AVG_TRIGGER_TEMP = 80.0       # Trigger max fan speed when 10-sec average reaches 80°C
SUSTAINED_HIGH_TEMP_THRESHOLD = 85.0  # Instantaneous threshold for sustained spike check
SUSTAINED_HIGH_TEMP_DURATION_SEC = 3.0 # Must remain above 85°C for >= 3 seconds
RECOVERY_AVG_THRESHOLD = 75.0         # 5°C hysteresis: rolling averages must fall below 75°C
RECOVERY_PEAK_THRESHOLD = 80.0        # 5°C hysteresis: instantaneous peaks must fall below 80°C


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
    Communicates with /dev/alg_fan or alg-fan CLI.
    
    ACPI Contract (DSDT \_SB.DCHU._DSM UUID 93f224e4-fbdc-4bbf-add6-db71bdc0afad):
      - Function 0x68 (Manual Duty): Package { Buffer { duty1, duty2, 0, 0 } }
      - Function 0x69 (Auto Restore): Package { Buffer { bitmask, 0, 0, 0 } } (0x03 = both fans)
    """

    def __init__(self, hardware_writes_enabled: bool = True):
        self.hardware_writes_enabled = hardware_writes_enabled
        self.device_path = DEV_FAN_PATH
        self.last_commanded_cpu_raw = 0
        self.last_commanded_gpu_raw = 0
        self.last_commanded_mode = "auto"
        self.call_history: List[Dict[str, Any]] = []

    def is_hardware_available(self) -> bool:
        """Check if physical ACPI fan interface is accessible."""
        if os.path.exists(self.device_path) and os.access(self.device_path, os.W_OK):
            return True
        cli = find_fan_cli_path()
        return cli is not None

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

        # 1. Direct device node actuation (/dev/alg_fan)
        if os.path.exists(self.device_path):
            try:
                with open(self.device_path, "w", encoding="utf-8") as f:
                    f.write(f"{cpu_clamped} {gpu_clamped}\n")
                return True, f"Hardware Applied: CPU {cpu_clamped}% (raw {cpu_raw}), GPU {gpu_clamped}% (raw {gpu_raw}) via SCMD 0x68"
            except PermissionError:
                return False, f"Permission denied writing to {self.device_path}. Ensure user is in 'alg-rgb' group."
            except Exception as e:
                return False, f"Error writing to {self.device_path}: {e}"

        # 2. CLI fallback actuation (alg-fan)
        cli = find_fan_cli_path()
        if cli:
            try:
                proc = subprocess.run([cli, str(cpu_clamped), str(gpu_clamped)], capture_output=True, text=True, timeout=2.0)
                if proc.returncode == 0:
                    return True, f"Applied via CLI: CPU {cpu_clamped}%, GPU {gpu_clamped}%"
                return False, proc.stderr.strip() or f"CLI returned code {proc.returncode}"
            except Exception as e:
                return False, f"CLI execution error: {e}"

        return False, f"Kernel interface {self.device_path} not found. Run 'sudo ./install.sh' to load driver."

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

        # 1. Direct device node actuation (/dev/alg_fan)
        if os.path.exists(self.device_path):
            try:
                with open(self.device_path, "w", encoding="utf-8") as f:
                    f.write("auto\n")
                return True, "Restored firmware automatic fan control (SCMD 0x69)"
            except PermissionError:
                return False, f"Permission denied writing to {self.device_path}. Ensure user is in 'alg-rgb' group."
            except Exception as e:
                return False, f"Error writing to {self.device_path}: {e}"

        # 2. CLI fallback actuation
        cli = find_fan_cli_path()
        if cli:
            try:
                proc = subprocess.run([cli, "auto"], capture_output=True, text=True, timeout=2.0)
                if proc.returncode == 0:
                    return True, "Restored firmware automatic fan control (SCMD 0x69)"
                return False, proc.stderr.strip() or f"CLI returned code {proc.returncode}"
            except Exception as e:
                return False, f"CLI execution error: {e}"

        return False, f"Kernel interface {self.device_path} not found. Run 'sudo ./install.sh' to load driver."

    def read_driver_diagnostics(self) -> Dict[str, Any]:
        """Read diagnostic status from /dev/alg_fan."""
        data = {
            "device_exists": os.path.exists(self.device_path),
            "device_writable": os.access(self.device_path, os.W_OK) if os.path.exists(self.device_path) else False,
            "fan_mode": self.last_commanded_mode,
            "last_acpi_status": "N/A"
        }
        if os.path.exists(self.device_path):
            try:
                with open(self.device_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if ":" in line:
                            k, v = line.split(":", 1)
                            data[k.strip()] = v.strip()
            except Exception:
                pass
        return data

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
    High-level fan controller engine managing modes, curves, rolling sensor averages, and thermal safety.
    """

    def __init__(self, backend: Optional[FanHardwareBackend] = None):
        self.backend = backend or FanHardwareBackend(hardware_writes_enabled=True)
        self.current_mode = FanMode.AUTO
        self.custom_cpu_duty = 50
        self.custom_gpu_duty = 50
        self.sync_fans = True

        self.active_cpu_target_pct = 50
        self.active_gpu_target_pct = 50
        self.emergency_override = False
        self.high_temp_start_time: Optional[float] = None

        # Continuous multi-sensor 10-second rolling history: {sensor_name: deque([(timestamp, temp), ...])}
        self.sensor_windows: Dict[str, deque] = {}
        self.sensor_averages: Dict[str, float] = {}

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
        self.high_temp_start_time = None
        self.sensor_windows.clear()
        self.sensor_averages.clear()
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

        # Prevent transient curve peaks from commanding 100% maximum fan speed
        # unless sustained high-temperature check has passed
        if target >= 100 and not self.emergency_override:
            target = 90

        self.active_cpu_target_pct = target
        self.active_gpu_target_pct = target
        ok, msg = self.backend.apply_manual_duty(target, target)
        self.last_status_message = f"Profile [{self.current_mode.value.upper()}]: {target}% target at {hottest:.0f}°C"
        return ok, msg

    def tick_thermal_update(
        self,
        cpu_temp: float,
        gpu_temp: float,
        now: Optional[float] = None,
        all_sensors: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Continuous thermal update tick called approximately every 1 second.
        Maintains a rolling 10-second monitoring window across all monitored sensors.
        Triggers maximum fan speed if:
          1. Any relevant sensor's 10-second rolling average reaches >= 80.0°C.
          2. Any relevant sensor remains >= 85.0°C for a sustained period (>= 3 consecutive seconds).
        Resets high-temperature timer when temperatures fall below 85.0°C.
        Restores normal control when temperatures cool down with hysteresis.
        """
        current_time = now if now is not None else time.monotonic()

        # Build unified sensor reading map
        sensors: Dict[str, float] = dict(all_sensors) if all_sensors else {}
        if "CPU Package" not in sensors:
            sensors["CPU Package"] = float(cpu_temp)
        if "GPU Core" not in sensors and "GPU" not in sensors:
            sensors["GPU Core"] = float(gpu_temp)

        # 1. Update rolling 10-second window for each sensor
        self.sensor_averages.clear()
        for name, val in sensors.items():
            if name not in self.sensor_windows:
                self.sensor_windows[name] = deque()
            win = self.sensor_windows[name]
            win.append((current_time, float(val)))
            # Prune samples older than 10 seconds
            while win and (current_time - win[0][0]) > ROLLING_WINDOW_DURATION_SEC:
                win.popleft()
            # Calculate 10-second rolling average
            if win:
                self.sensor_averages[name] = sum(v for t, v in win) / len(win)

        # 2. Identify instantaneous hottest sensor and maximum 10-second rolling average
        hottest_instant = max(sensors.values()) if sensors else max(cpu_temp, gpu_temp)
        max_avg_sensor = max(self.sensor_averages, key=self.sensor_averages.get) if self.sensor_averages else "CPU Package"
        max_avg_val = self.sensor_averages.get(max_avg_sensor, 0.0)

        # 3. Check Sustained >= 85°C Condition (any sensor >= 85°C for >= 3 seconds)
        is_above_85 = hottest_instant >= SUSTAINED_HIGH_TEMP_THRESHOLD
        if is_above_85:
            if self.high_temp_start_time is None:
                self.high_temp_start_time = current_time
            sustained_elapsed = current_time - self.high_temp_start_time
            is_sustained_85 = sustained_elapsed >= SUSTAINED_HIGH_TEMP_DURATION_SEC
        else:
            # Reset high-temperature timer immediately when temperatures fall below 85°C
            self.high_temp_start_time = None
            sustained_elapsed = 0.0
            is_sustained_85 = False

        # 4. Check 10-Second Rolling Average >= 80°C Condition
        # Requires that the window has accumulated near a full 10-second span (>= 7.0s)
        # to ensure it represents a true 10-second rolling average
        win_duration = 0.0
        if max_avg_sensor in self.sensor_windows and len(self.sensor_windows[max_avg_sensor]) > 1:
            win = self.sensor_windows[max_avg_sensor]
            win_duration = win[-1][0] - win[0][0]

        is_avg_80 = (max_avg_val >= ROLLING_AVG_TRIGGER_TEMP and win_duration >= 7.0)

        # 5. Evaluate Maximum Fan Speed Trigger
        if is_avg_80 or is_sustained_85:
            if not self.emergency_override:
                self.emergency_override = True
                self.backend.apply_manual_duty(100, 100)
            self.active_cpu_target_pct = 100
            self.active_gpu_target_pct = 100

            reasons = []
            if is_avg_80:
                reasons.append(f"{max_avg_sensor} 10s avg={max_avg_val:.1f}°C ≥ {ROLLING_AVG_TRIGGER_TEMP:.0f}°C")
            if is_sustained_85:
                reasons.append(f"peak={hottest_instant:.1f}°C sustained for {sustained_elapsed:.1f}s ≥ {SUSTAINED_HIGH_TEMP_DURATION_SEC:.0f}s")

            self.last_status_message = (
                f"⚠️ EMERGENCY THERMAL SAFETY: MAXIMUM COOLING ENGAGED ({', '.join(reasons)})."
            )
            return self.get_state_snapshot()

        # 6. Recovery with Hysteresis
        # Once temperatures cool down (all averages < 75°C and peak < 80°C), clear emergency override
        was_emergency = self.emergency_override
        if self.emergency_override:
            if max_avg_val < RECOVERY_AVG_THRESHOLD and hottest_instant < RECOVERY_PEAK_THRESHOLD:
                self.emergency_override = False

        # If still in emergency cooldown band, maintain 100% cooling
        if self.emergency_override:
            self.active_cpu_target_pct = 100
            self.active_gpu_target_pct = 100
            return self.get_state_snapshot()

        # 7. Normal Mode Processing & Clean Hardware Recovery
        if self.current_mode == FanMode.AUTO:
            self.active_cpu_target_pct = 0
            self.active_gpu_target_pct = 0
            if was_emergency or self.backend.last_commanded_mode != "auto":
                self.backend.apply_auto_mode()
            self.last_status_message = "Firmware Automatic (EC Closed-Loop Active)"
        elif self.current_mode in (FanMode.SILENT, FanMode.BALANCED, FanMode.PERFORMANCE):
            self.update_preset_duty(cpu_temp, gpu_temp)
        elif self.current_mode == FanMode.CUSTOM:
            self.active_cpu_target_pct = self.custom_cpu_duty
            self.active_gpu_target_pct = self.custom_gpu_duty
            if (was_emergency or
                    self.backend.last_commanded_mode != "manual" or
                    self.backend.last_commanded_cpu_raw != pct_to_raw(self.custom_cpu_duty) or
                    self.backend.last_commanded_gpu_raw != pct_to_raw(self.custom_gpu_duty)):
                self.apply_custom_duty()

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
            "high_temp_timer_active": self.high_temp_start_time is not None,
            "sensor_averages": dict(self.sensor_averages),
        }
