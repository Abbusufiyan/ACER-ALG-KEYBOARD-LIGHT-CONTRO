"""
Hardware backend interface for Acer ALG RGB.
Interfaces directly with the alg-rgb CLI and reads diagnostic data from /dev/alg_rgb.
"""

import os
import shutil
import subprocess
from typing import Tuple, Dict, Any, Optional

DEV_PATH = "/dev/alg_rgb"
ACPI_CLV1 = "/sys/bus/acpi/devices/CLV0001:00"
MODULE_PATH = "/sys/module/alg_rgb"


def find_cli_path() -> Optional[str]:
    """Find the alg-rgb CLI binary in PATH or known installation locations."""
    # Check standard install path
    if os.path.isfile("/usr/local/bin/alg-rgb") and os.access("/usr/local/bin/alg-rgb", os.X_OK):
        return "/usr/local/bin/alg-rgb"

    # Check system PATH
    which_path = shutil.which("alg-rgb")
    if which_path and os.access(which_path, os.X_OK):
        return which_path

    # Fallback to local build in ~/alg-cli/cli/alg-rgb
    local_path = os.path.expanduser("~/alg-cli/cli/alg-rgb")
    if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
        return local_path

    return None


def apply_color(color_name: str, brightness: int) -> Tuple[bool, str]:
    """
    Safely execute the alg-rgb CLI to set keyboard RGB color and brightness.
    Returns (success: bool, message: str).
    """
    cli = find_cli_path()
    if not cli:
        return False, "The 'alg-rgb' CLI utility is not installed or not in PATH."

    brightness = max(0, min(4, int(brightness)))

    cmd = [cli, color_name.strip().lower(), str(brightness)]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=4.0,
            check=False
        )
        if proc.returncode == 0:
            msg = proc.stdout.strip() or f"Color '{color_name}' applied at brightness {brightness}."
            return True, msg
        else:
            err = proc.stderr.strip() or proc.stdout.strip() or f"Command failed with exit code {proc.returncode}."
            return False, err
    except subprocess.TimeoutExpired:
        return False, "Command timed out while waiting for ACPI/firmware."
    except Exception as ex:
        return False, f"Execution error: {str(ex)}"


def turn_off() -> Tuple[bool, str]:
    """
    Safely execute the alg-rgb CLI to power off the keyboard RGB lighting.
    Returns (success: bool, message: str).
    """
    cli = find_cli_path()
    if not cli:
        return False, "The 'alg-rgb' CLI utility is not installed or not in PATH."

    cmd = [cli, "off"]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=4.0,
            check=False
        )
        if proc.returncode == 0:
            return True, "Keyboard lighting powered off."
        else:
            err = proc.stderr.strip() or proc.stdout.strip() or f"Command failed with code {proc.returncode}."
            return False, err
    except Exception as ex:
        return False, f"Execution error: {str(ex)}"


def read_diagnostics() -> Dict[str, Any]:
    """
    Read real-time diagnostic status from /dev/alg_rgb, kernel sysfs, and DMI.
    Does not issue any hardware write commands.
    """
    diag: Dict[str, Any] = {
        "device_exists": os.path.exists(DEV_PATH),
        "device_readable": os.access(DEV_PATH, os.R_OK) if os.path.exists(DEV_PATH) else False,
        "device_writable": os.access(DEV_PATH, os.W_OK) if os.path.exists(DEV_PATH) else False,
        "module_loaded": os.path.exists(MODULE_PATH),
        "acpi_clv1_present": os.path.exists(ACPI_CLV1),
        "cli_path": find_cli_path(),
        "driver_version": "unknown",
        "last_acpi_status": -1,
        "last_acpi_desc": "Unknown",
        "software_state": "UNKNOWN",
        "last_color": "none",
        "last_brightness": -1,
        "hardware_confirmation": "UNVERIFIED",
        "raw_text": ""
    }

    if diag["device_readable"]:
        try:
            with open(DEV_PATH, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                diag["raw_text"] = content
                for line in content.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip()
                        v = v.strip()
                        if k == "driver_version":
                            diag["driver_version"] = v
                        elif k == "last_acpi_status":
                            diag["last_acpi_desc"] = v
                            try:
                                # v format: '0 (SUCCESS...)' or '-61 (UNTESTED...)'
                                diag["last_acpi_status"] = int(v.split()[0])
                            except Exception:
                                pass
                        elif k == "software_state":
                            diag["software_state"] = v
                        elif k == "last_requested_color":
                            diag["last_color"] = v
                        elif k == "last_requested_brightness":
                            try:
                                diag["last_brightness"] = int(v)
                            except Exception:
                                pass
                        elif k == "hardware_confirmation":
                            diag["hardware_confirmation"] = v
        except Exception as e:
            diag["read_error"] = str(e)

    return diag
