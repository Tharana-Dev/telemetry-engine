from engine.models import ThermalSnapshot, GpuInfo
import subprocess
import json
import pynvml
import time
import os
from engine.logger import logger


CPU_LOOKUP = {
    "coretemp": "Intel",
    "k10temp": "AMD",
    "zenpower": "AMD",
}

# Substring mapping for top motherboard / laptop brands.
BOARD_LOOKUP = {
    "thinkpad": "Lenovo (ThinkPad)",
    "dell_smm": "Dell",
    "asus": "ASUS",
    "hp": "HP",
    "applesmc": "Apple",
    "acer": "Acer",
    "fujitsu": "Fujitsu",
    "toshiba": "Toshiba",
    "gigabyte": "Gigabyte",
    "msi": "MSI",
}


class LinuxThermalSampler:

    def __init__(self) -> None:
        self.initialized = False
        self._last_thermal_time = 0.0
        self._cached_snapshot: ThermalSnapshot | None = None
        
        # --- NEW: Cache static hardware info on startup ---
        self._cpu_name, self._cpu_speed_mhz = self._get_cpu_info()
        self._board_vendor = self._get_board_info()
        self._igpu_name = self._get_igpu_name()
        
        try:
            pynvml.nvmlInit()
            self.initialized = True
        except Exception:
            self.initialized = False

    def __del__(self):
        if self.initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass

    # =================================================================
    # NEW HELPER METHODS (Run once at startup)
    # =================================================================

    def _get_cpu_info(self) -> tuple[str | None, int | None]:
        name = None
        speed_mhz = None
        
        # 1. Try to get the base speed from sysfs (stable, doesn't fluctuate)
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/base_frequency", "r") as f:
                speed_mhz = int(int(f.read().strip()) / 1000)
        except (FileNotFoundError, ValueError, PermissionError):
            pass
            
        # 2. Read /proc/cpuinfo for the model name and fallback speed
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name") and not name:
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("cpu MHz") and speed_mhz is None:
                        try:
                            speed_mhz = int(float(line.split(":", 1)[1].strip()))
                        except ValueError:
                            pass
                    if name and speed_mhz:
                        break
        except (FileNotFoundError, PermissionError):
            pass
            
        return name, speed_mhz

    def _get_board_info(self) -> str | None:
        vendor = None
        name = None
        
        try:
            with open("/sys/class/dmi/id/board_vendor", "r") as f:
                vendor = f.read().strip()
        except (FileNotFoundError, PermissionError):
            pass
            
        try:
            with open("/sys/class/dmi/id/board_name", "r") as f:
                name = f.read().strip()
        except (FileNotFoundError, PermissionError):
            pass
            
        if vendor and name:
            return f"{vendor} {name}"
        return vendor or name

    def _get_igpu_name(self) -> str | None:
        try:
            kwargs = {}
            if os.name == 'nt':
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            res = subprocess.run(["lspci"], capture_output=True, text=True, check=True, timeout=2, **kwargs)
            for line in res.stdout.splitlines():
                # Look for VGA or Display controllers
                if "VGA compatible controller" in line or "Display controller" in line:
                    # Filter for known GPU keywords
                    if any(kw in line for kw in ["Intel", "AMD", "Radeon", "Adreno"]):
                        # Format: "00:02.0 VGA compatible controller: Intel Corporation ..."
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            return parts[2].strip()
        except Exception:
            pass
        return None

    # =================================================================
    # EXISTING METHODS
    # =================================================================

    def _get_nvidia(self) -> list[GpuInfo]:
        if not self.initialized:
            try:
                pynvml.nvmlInit()
                self.initialized = True
            except Exception as e:
                logger.error(f"NVML init failed: {e}")
                return []

        try:
            count = pynvml.nvmlDeviceGetCount()
        except pynvml.NVMLError as e:
            logger.error(f"NVML driver lost. Attempting to reset: {e}")
            self.initialized = False
            return []
            
        if count == 0:
            return []

        gpu_records: list[GpuInfo] = []
        for i in range(count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")

                try:
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except pynvml.NVMLError:
                    temp = None

                try:
                    usage = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                except pynvml.NVMLError:
                    usage = None

                try:
                    power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                    power_watts = round(power_mw / 1000, 2)
                    # Add sanity check:
                    if power_watts > 250.0:
                        power_watts = None
                except pynvml.NVMLError:
                    power_watts = None

                try:
                    fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                except pynvml.NVMLError:
                    fan_speed = None

                gpu_records.append(GpuInfo(
                    index=i,
                    name=name,
                    temperature_c=temp,
                    utilization_pct=usage,
                    power_w=power_watts,
                    fan_speed_pct=fan_speed,
                ))
            except Exception:
                continue

        return gpu_records

    def _get_sensors(self) -> dict | None:
        try:
            # FIX: CREATE_NO_WINDOW crashes on Linux. Only pass it if on Windows.
            kwargs = {}
            if os.name == 'nt':
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                
            res = subprocess.run(
                ["sensors", "-j"],
                capture_output=True,
                text=True,
                check=True,
                timeout=2,
                **kwargs
            )
        except (FileNotFoundError, PermissionError,
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired):
            return None
        except Exception:
            return None

        try:
            data = json.loads(res.stdout)
        except json.decoder.JSONDecodeError:
            return None

        cpu_temp = None
        cpu_max = None
        fans: dict[str, int] = {}
        cpu_vendor = None
        board_vendor = None

        for driver_name, driver_data in data.items():
            if not isinstance(driver_data, dict):
                continue

            for search_key, vendor in CPU_LOOKUP.items():
                if search_key in driver_name:
                    cpu_vendor = vendor
                    if "Package id 0" in driver_data:
                        package_data = driver_data.get("Package id 0", {})
                        cpu_temp = package_data.get("temp1_input")
                        cpu_max = package_data.get("temp1_max")
                    elif "Tctl" in driver_data:
                        cpu_temp = driver_data["Tctl"].get("temp1_input")
                    break

            for search_key, vendor in BOARD_LOOKUP.items():
                if search_key in driver_name:
                    board_vendor = vendor
                    break

            for key, value in driver_data.items():
                if key.startswith("fan"):
                    input_key = f"{key}_input"
                    if isinstance(value, dict) and input_key in value:
                        fans[key] = value[input_key]

        return {
            "cpu_temp": cpu_temp,
            "cpu_max": cpu_max,
            "system_fans": fans,
            "cpu_vendor": cpu_vendor,
            "board_vendor": board_vendor,
        }

    def get_thermal_snapshot(self) -> ThermalSnapshot:
        now = time.monotonic()
        if self._cached_snapshot is not None and (now - self._last_thermal_time) < 3.0:
            return self._cached_snapshot

        gpus = self._get_nvidia()
        sensor_data = self._get_sensors()

        cpu_temp = None
        cpu_max = None
        system_fans = None
        cpu_vendor = None
        sensor_board_vendor = None

        if sensor_data is not None:
            cpu_temp = sensor_data["cpu_temp"]
            cpu_max = sensor_data["cpu_max"]

            raw_fans = sensor_data["system_fans"] or {}
            if raw_fans:
                converted: dict[str, int] = {}
                for k, v in raw_fans.items():
                    try:
                        converted[k] = int(float(v))
                    except (ValueError, TypeError):
                        pass
                system_fans = converted or None

            cpu_vendor = sensor_data["cpu_vendor"]
            sensor_board_vendor = sensor_data["board_vendor"]

        snapshot = ThermalSnapshot(
            cpu_temp=cpu_temp,
            cpu_temp_max=cpu_max,
            system_fans=system_fans,
            gpus=gpus,
            gpu_available=bool(gpus),
            sensor_available=sensor_data is not None,
            cpu_vendor=cpu_vendor,
            # Use DMI board_vendor first, fallback to sensors mapping
            board_vendor=self._board_vendor or sensor_board_vendor,
            
            cpu_name=self._cpu_name,
            cpu_base_speed_mhz= self._cpu_speed_mhz,
            igpu_name=self._igpu_name,
        )

        self._cached_snapshot = snapshot
        self._last_thermal_time = now
        return snapshot