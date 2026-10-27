"""
Hardware Thermal and Sensor Monitoring Engine for Acer ALG AL15G-52.
Reads CPU core temperatures (coretemp), NVIDIA GPU telemetry (nvidia-smi),
NVMe SSD temperatures, and ACPI thermal zones safely without privileged/dangerous EC writes.
"""

import os
import glob
import subprocess
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class CpuCoreTemp:
    label: str
    temp_c: float
    crit_c: float = 100.0


@dataclass
class CpuTelemetry:
    package_temp: float = 0.0
    cores: List[CpuCoreTemp] = field(default_factory=list)
    max_core_temp: float = 0.0
    avg_core_temp: float = 0.0
    crit_threshold: float = 100.0
    sensor_found: bool = False


@dataclass
class GpuTelemetry:
    available: bool = False
    name: str = "NVIDIA GeForce RTX 2050"
    temp_c: float = 0.0
    utilization_pct: int = 0
    power_draw_w: float = 0.0
    vram_used_mb: int = 0
    vram_total_mb: int = 0
    driver_version: str = ""


@dataclass
class FanHardwareStatus:
    mode: str = "Automatic (EC Firmware Managed)"
    manual_control_supported: bool = False
    protection_active: bool = True
    detected_fans: int = 2
    hardware_notes: str = (
        "The Acer ALG AL15G-52 Embedded Controller autonomously regulates cooling "
        "using internal BIOS thermal curves. No standard Linux hwmon PWM control "
        "is exposed by kernel drivers for this chassis."
    )


class SensorEngine:
    def __init__(self):
        self._coretemp_path: Optional[str] = self._locate_coretemp_hwmon()

    def _locate_coretemp_hwmon(self) -> Optional[str]:
        for path in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                name_file = os.path.join(path, "name")
                if os.path.isfile(name_file):
                    with open(name_file, "r", encoding="utf-8") as f:
                        if f.read().strip() == "coretemp":
                            return path
            except Exception:
                pass
        return None

    def read_cpu_telemetry(self) -> CpuTelemetry:
        telemetry = CpuTelemetry()
        if not self._coretemp_path or not os.path.isdir(self._coretemp_path):
            self._coretemp_path = self._locate_coretemp_hwmon()

        if not self._coretemp_path:
            return telemetry

        telemetry.sensor_found = True
        cores_list: List[CpuCoreTemp] = []

        try:
            for input_path in glob.glob(os.path.join(self._coretemp_path, "temp*_input")):
                prefix = input_path[:-6]
                label_path = prefix + "_label"
                crit_path = prefix + "_crit"

                label = "Unknown"
                if os.path.isfile(label_path):
                    with open(label_path, "r", encoding="utf-8") as f:
                        label = f.read().strip()

                temp_val = 0.0
                with open(input_path, "r", encoding="utf-8") as f:
                    temp_val = float(f.read().strip()) / 1000.0

                crit_val = 100.0
                if os.path.isfile(crit_path):
                    try:
                        with open(crit_path, "r", encoding="utf-8") as f:
                            crit_val = float(f.read().strip()) / 1000.0
                    except Exception:
                        pass

                if "Package" in label:
                    telemetry.package_temp = temp_val
                    telemetry.crit_threshold = crit_val
                else:
                    cores_list.append(CpuCoreTemp(label=label, temp_c=temp_val, crit_c=crit_val))

            if cores_list:
                # Sort cores by numeric core index if possible
                def core_sort_key(c: CpuCoreTemp) -> int:
                    try:
                        return int(c.label.split()[-1])
                    except Exception:
                        return 0

                cores_list.sort(key=core_sort_key)
                telemetry.cores = cores_list
                temps = [c.temp_c for c in cores_list]
                telemetry.max_core_temp = max(temps)
                telemetry.avg_core_temp = sum(temps) / len(temps)
                if telemetry.package_temp == 0.0:
                    telemetry.package_temp = telemetry.max_core_temp

        except Exception:
            pass

        return telemetry

    def read_gpu_telemetry(self) -> GpuTelemetry:
        gpu = GpuTelemetry()
        try:
            # Query nvidia-smi with a strict 1s timeout
            res = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=temperature.gpu,utilization.gpu,power.draw,memory.used,memory.total,driver_version",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 5:
                    gpu.available = True
                    gpu.temp_c = float(parts[0])
                    gpu.utilization_pct = int(parts[1])
                    gpu.power_draw_w = float(parts[2])
                    gpu.vram_used_mb = int(parts[3])
                    gpu.vram_total_mb = int(parts[4])
                    if len(parts) >= 6:
                        gpu.driver_version = parts[5]
        except Exception:
            gpu.available = False

        return gpu

    def read_auxiliary_temperatures(self) -> Dict[str, float]:
        """Read temperatures for NVMe, ACPI thermal zones, and Wi-Fi adapter."""
        results: Dict[str, float] = {}
        for hw in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                name_file = os.path.join(hw, "name")
                if not os.path.isfile(name_file):
                    continue
                with open(name_file, "r", encoding="utf-8") as f:
                    name = f.read().strip()

                temp_file = os.path.join(hw, "temp1_input")
                if not os.path.isfile(temp_file):
                    continue

                with open(temp_file, "r", encoding="utf-8") as f:
                    val = float(f.read().strip()) / 1000.0

                if name == "nvme":
                    results["NVMe SSD"] = val
                elif name == "acpitz":
                    results["ACPI Motherboard"] = val
                elif name.startswith("iwlwifi"):
                    results["Wi-Fi Module"] = val
            except Exception:
                pass

        return results

    def get_fan_hardware_status(self) -> FanHardwareStatus:
        """Inspect whether any standard hwmon pwm control is available."""
        has_pwm = False
        for hw in glob.glob("/sys/class/hwmon/hwmon*"):
            if glob.glob(os.path.join(hw, "pwm*")):
                has_pwm = True
                break

        return FanHardwareStatus(
            mode="Firmware Automatic (EC Managed)",
            manual_control_supported=has_pwm,
            protection_active=True,
            detected_fans=2
        )
