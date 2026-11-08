from engine.models import ThermalSnapshot, GpuInfo
import subprocess
import json
import pynvml
import time
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
        try:
            pynvml.nvmlInit()
            self.initialized = True
        except Exception:
            # No usable NVIDIA driver (library missing, driver not loaded,
            # post-reset, patched runtime, …). Rule 3: no GPU hardware →
            # gpu_available=False in the snapshot. The thermal sampler has
            # no single primary source, so this is not fatal.
            self.initialized = False

    def __del__(self):
        if self.initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass

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
            # The driver crashed or powered off mid-session!
            logger.error(f"NVML driver lost. Attempting to reset: {e}")
            self.initialized = False  # <--- CRITICAL FIX: Force re-init next tick
            return []
        if count == 0:
            return []

        gpu_records: list[GpuInfo] = []
        for i in range(count):
            # T1: per-GPU isolation. A single bad GPU must not drop the
            # data already collected for earlier GPUs.
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")

                try:
                    temp = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                except pynvml.NVMLError:
                    temp = None

                try:
                    usage = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                except pynvml.NVMLError:
                    usage = None

                # Power is returned in milliwatts.
                try:
                    power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                    power_watts = round(power_mw / 1000, 2)
                except pynvml.NVMLError:
                    power_watts = None

                try:
                    fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                except pynvml.NVMLError:
                    # EC owns the fan (common on laptops), or a transient
                    # driver error — either way, "not available" is honest.
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
                # T1: skip this GPU; keep whatever we already collected.
                continue

        return gpu_records

    def _get_sensors(self) -> dict | None:
        # Best-effort probe of the `sensors` binary. Any subprocess failure
        # means "no usable sensor data" → None → sensor_available=False.
        # The thermal sampler has no primary source, so nothing here is
        # fatal.
        try:
            res = subprocess.run(
                ["sensors", "-j"],
                capture_output=True,
                text=True,
                check=True,
                timeout=2,
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

        # Partial: sensors ran and returned parseable JSON, but individual
        # fields may still be None.
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
        board_vendor = None

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
            board_vendor = sensor_data["board_vendor"]

        snapshot = ThermalSnapshot(
            cpu_temp=cpu_temp,
            cpu_temp_max=cpu_max,
            system_fans=system_fans,
            gpus=gpus,
            gpu_available=bool(gpus),
            sensor_available=sensor_data is not None,
            cpu_vendor=cpu_vendor,
            board_vendor=board_vendor,
        )

        self._cached_snapshot = snapshot
        self._last_thermal_time = now
        return snapshot