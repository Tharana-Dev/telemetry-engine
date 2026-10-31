from engine.models import ThermalSnapshot
import subprocess
from dataclasses import dataclass
import json
from typing import Any
from enum import Enum
import pynvml

CPU_LOOKUP = {
    "coretemp": "Intel",
    "k10temp": "AMD",
    "zenpower": "AMD"
}

# Substring mapping for Top Motherboard / Laptop Brands
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
    "msi": "MSI"
}

#external cofig O(1) lookup to be implemented

class ThermalError(Enum):
    NOT_FOUND = "NVIDIA tool or sensors command not found."
    NOT_PRESENT = "No NVIDIA GPU detected or driver not installed."
    BROKEN_DRIVER = "Driver crashed or returned an error code."
    TIMEOUT = "Hardware query timed out."
    PARSE_FAILED = "Could not parse hardware output (format changed)."
    UNKNOWN = "An unknown error occurred."
    PYNVML_ERROR = "NVMLError Occurred"


@dataclass(frozen=True)
class InternalResult:
    data: dict[str, Any] | None = None
    error: ThermalError | None = None

class LinuxThermalSampler:
    
    def _get_nvidia(self) -> InternalResult:
        initialized = False
        try:
            pynvml.nvmlInit()
            initialized = True

            count = pynvml.nvmlDeviceGetCount()
            if count == 0:
                return InternalResult(error=ThermalError.NOT_PRESENT)

            gpu_records = []
            NotSupportedError = getattr(pynvml, "NVMLError_NotSupported", pynvml.NVMLError)

            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")

                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                usage = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                
                # Power is returned in milliwatts. Convert to Watts.
                power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                power_watts = round(power_mw / 1000, 2)

                fan_speed = None
                try:
                    fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                except NotSupportedError:
                    # EC owns the fan (common on laptops)
                    pass 

                gpu_data = {
                    "index": i,
                    "name": name,
                    "temperature_c": temp,
                    "utilization_pct": usage,
                    "power_w": power_watts,
                    "fan_speed_pct": fan_speed
                }
                gpu_records.append(gpu_data)
                
            return InternalResult(data={"gpus": gpu_records})
        
        except pynvml.NVMLError:
            return InternalResult(error=ThermalError.PYNVML_ERROR)
        finally:
            if initialized:
                try:
                    pynvml.nvmlShutdown()
                except pynvml.NVMLError:
                    pass

        
    def _get_sensors(self):
        try:
            res = subprocess.run(
            ["sensors", "-j"], 
            capture_output=True, 
            text=True, 
            check=True, 
            timeout=2
        )
            
            data = json.loads(res.stdout)
            
            cpu_temp = None
            cpu_max = None
            fans = {}
            cpu_vendor = "Unknown"
            board_vendor = "Unknown"
            
            for driver_name, driver_data in data.items():
                if not isinstance(driver_data,dict):
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
                        break # Stop looking once found

                # 3. Extract Fans
                for key, value in driver_data.items():
                    if key.startswith("fan"):
                        input_key = f"{key}_input"
                        if isinstance(value, dict) and input_key in value:
                            fans[key] = value[input_key]
                            
            sensor_data = {
                "cpu_temp": cpu_temp,
                "cpu_max": cpu_max,
                "system_fans": fans,
                "cpu_vendor": cpu_vendor,
                "board_vendor": board_vendor
            }
            
            return InternalResult(data=sensor_data)
            
        except FileNotFoundError:
            return InternalResult(error=ThermalError.NOT_PRESENT)
        except subprocess.CalledProcessError:
            return InternalResult(error=ThermalError.BROKEN_DRIVER)
        except subprocess.TimeoutExpired:
            return InternalResult(error=ThermalError.TIMEOUT)
        except (json.decoder.JSONDecodeError, KeyError, IndexError):
            return InternalResult(error=ThermalError.PARSE_FAILED)
        except Exception:
            return InternalResult(error=ThermalError.UNKNOWN)
        
    def get_thermal_snapshot(self) -> ThermalSnapshot:
        gpu_data = self._get_nvidia()
        sensor_data = self._get_sensors()
        
        cpu_temp = None
        cpu_max = None
        system_fans = None
        cpu_vendor = "Unknown"
        board_vendor = "Unknown"
        gpu_error = None
        sensor_error = None
        
        # --- Handle GPU ---
        gpus_list = []
        if gpu_data.data and "gpus" in gpu_data.data:
            gpus_list = gpu_data.data["gpus"]
            if not gpus_list:
                gpu_error = "No GPU devices found"
        else:
            gpu_error = gpu_data.error.value if gpu_data.error else "Unknown Error"

        # --- Handle Sensors ---
        if sensor_data.data:
            cpu_temp = sensor_data.data['cpu_temp']
            cpu_max = sensor_data.data['cpu_max']
            
            # Safely convert fans to int if they exist
            if sensor_data.data['system_fans']:
                system_fans = {}
                for k, v in sensor_data.data['system_fans'].items():
                    try:
                        system_fans[k] = int(float(v))
                    except (ValueError, TypeError):
                        pass # Skip the fan if it's [N/A] or malformed
            if not system_fans:
                system_fans = None
            
            cpu_vendor = sensor_data.data.get('cpu_vendor', 'Unknown')
            board_vendor = sensor_data.data.get('board_vendor', 'Unknown')
        else:
            sensor_error = sensor_data.error.value if sensor_data.error else "Unknown Error"
        
        # The dataclass's __post_init__ will automatically map the legacy single-GPU 
        # properties (gpu_temp, gpu_fan, etc.) from the first item in this gpus list.
        return ThermalSnapshot(
            cpu_temp=cpu_temp,
            cpu_temp_max=cpu_max,
            system_fans=system_fans,
            gpus=gpus_list, 
            gpu_available=gpu_data.data is not None,
            sensor_available=sensor_data.data is not None,
            cpu_vendor=cpu_vendor,
            board_vendor=board_vendor,
            gpu_error=gpu_error,
            sensor_error=sensor_error
        )
