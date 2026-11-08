import ctypes
import platform
from engine.logger import logger
from engine.models import ThermalSnapshot, GpuInfo
import pynvml

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


class UniversalThermalSampler:
    def __init__(self):
        self._admin = is_admin()
        self._wintmp_available = False
        
        self._cpu_name = None
        self._cpu_speed_mhz = None
        self._board_vendor = None
        self._igpu_name = None
        self._cpu_vendor = "Unknown"

        if HAS_WINREG:
            try:
                path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ) as key:
                    name_data, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                    speed_data, _ = winreg.QueryValueEx(key, "~MHz")
                    self._cpu_name = name_data.strip()
                    self._cpu_speed_mhz = speed_data
                    
                    if "AMD" in self._cpu_name:
                        self._cpu_vendor = "AMD"
                    elif "Intel" in self._cpu_name:
                        self._cpu_vendor = "Intel"
            except Exception:
                pass

        if HAS_WMI:
            try:
                c = wmi.WMI()
                for board in c.Win32_BaseBoard():
                    vendor = board.Manufacturer.strip() if board.Manufacturer else ""
                    model = board.Product.strip() if board.Product else ""
                    self._board_vendor = f"{vendor} {model}".strip()

                for gpu in c.Win32_VideoController():
                    name = gpu.Name or ""
                    if any(keyword in name for keyword in ["Intel", "Radeon", "AMD", "Adreno"]):
                        self._igpu_name = name.strip()
                        break
            except Exception:
                pass        

        if self._admin:
            try:
                import WinTmp
                self._wintmp = WinTmp
                self._wintmp_available = True
            except Exception as e:
                logger.error(f"WinTmp failed to load: {e}")
        else:
            logger.warning("App started without Administrator privileges. CPU temperatures will be unavailable.")
            
        self.initialized = False
        self._last_thermal_time = 0.0
        self._cached_snapshot: ThermalSnapshot | None = None
        
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

                try: temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except pynvml.NVMLError: temp = None

                try: usage = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                except pynvml.NVMLError: usage = None
                    
                try:
                    power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                    power_watts = round(power_mw / 1000, 2)
                except pynvml.NVMLError: power_watts = None

                try: fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                except pynvml.NVMLError: fan_speed = None

                gpu_records.append(GpuInfo(
                    index=i, name=name, temperature_c=temp,
                    utilization_pct=usage, power_w=power_watts, fan_speed_pct=fan_speed,
                ))
            except Exception:
                continue
        return gpu_records

    def get_thermal_snapshot(self) -> ThermalSnapshot:
        gpus = self._get_nvidia()
        
        cpu_temp = None
        sensor_error = None
        
        if self._wintmp_available:
            try:
                cpu_temp = self._wintmp.CPU_Temp()
            except Exception:
                pass
        else:
            sensor_error = "Admin privileges required for CPU Temp"
            
        return ThermalSnapshot(
            cpu_temp=cpu_temp,
            cpu_temp_max=None,       # WinTmp doesn't provide max
            system_fans=None,        # WinTmp doesn't provide fans
            gpus=gpus,
            gpu_available=bool(gpus),
            sensor_available=(cpu_temp is not None or bool(gpus)),
            sensor_error=sensor_error,
            cpu_vendor=self._cpu_vendor,
            cpu_name=self._cpu_name,
            cpu_speed_mhz=self._cpu_speed_mhz,
            board_vendor=self._board_vendor,
            igpu_name=self._igpu_name
        )