from engine.models import ThermalSnapshot
import subprocess
from dataclasses import dataclass
import json
from typing import Any
from enum import Enum

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
    BROKEN_DRIVER = "Driver crashed or returned an error code."
    TIMEOUT = "Hardware query timed out."
    PARSE_FAILED = "Could not parse hardware output (format changed)."
    UNKNOWN = "An unknown error occurred."


@dataclass(frozen=True)
class InternalResult:
    data: dict[str, Any] | None = None
    error: ThermalError | None = None

class LinuxThermalSampler:
    def __init__(self):...
    
    def _get_nvidia(self) -> InternalResult:
        try:
            res = subprocess.run(
                ['nvidia-smi', '--query-gpu=temperature.gpu,fan.speed', '--format=json'],
                capture_output=True,
                text=True,
                timeout=2,
                check=True
            )
        
            data = json.loads(res.stdout)
            # TODO: Support multi-GPU setups
            gpu_temp = data['gpu'][0]['temperature']['gpu']
            gpu_fan = str(data['gpu'][0]['fan']['speed'])
            
            clean_fan = gpu_fan.replace("%", "").strip()

            if clean_fan.isdigit():
                gpu_fan = int(clean_fan)
            else:
                gpu_fan = None

            nvidia_results = {
                "temp": gpu_temp,
                "fan": gpu_fan
            }
            
            return InternalResult(data=nvidia_results)
            
        except FileNotFoundError:
            return InternalResult(error=ThermalError.NOT_FOUND)
        except subprocess.CalledProcessError:
            return InternalResult(error=ThermalError.BROKEN_DRIVER)
        except subprocess.TimeoutExpired:
            return InternalResult(error=ThermalError.TIMEOUT)
        except (json.decoder.JSONDecodeError, KeyError, IndexError):
            return InternalResult(error=ThermalError.PARSE_FAILED)
        except Exception:
            return InternalResult(error=ThermalError.UNKNOWN)
        
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
            return InternalResult(error=ThermalError.NOT_FOUND)
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
        gpu_temp = None
        gpu_fan = None
        cpu_vendor = "Unknown"
        board_vendor = "Unknown"
        gpu_error = None
        sensor_error = None
        
        # --- Handle GPU ---
        if gpu_data.data:
            gpu_temp = gpu_data.data['temp']
            gpu_fan = gpu_data.data['fan']
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
            
            cpu_vendor = sensor_data.data.get('cpu_vendor', 'Unknown')
            board_vendor = sensor_data.data.get('board_vendor', 'Unknown')
        else:
            sensor_error = sensor_data.error.value if sensor_data.error else "Unknown Error"
        
        return ThermalSnapshot(
            cpu_temp=cpu_temp,
            cpu_temp_max=cpu_max,
            system_fans=system_fans,
            gpu_temp=gpu_temp,
            gpu_fan=gpu_fan,
            gpu_available=bool(gpu_data.data),     
            sensor_available=bool(sensor_data.data),
            cpu_vendor=cpu_vendor,
            board_vendor=board_vendor,
            gpu_error=gpu_error,
            sensor_error=sensor_error
        )