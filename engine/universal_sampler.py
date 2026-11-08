from engine.models import (
    BatterySnapshot, CpuSnapshot, DiskIOSnapshot, MemorySnapshot, 
    NetworkSnapshot, ThermalSnapshot, DiskSpaceSnapshot
)
from engine.base_sampler import BaseSystemCollector
from engine.universal_impl.universal_disk import UniversalDiskSampler
from engine.universal_impl.universal_network import UniversalNetworkSampler
import psutil


class PsutilCollector(BaseSystemCollector):
    def __init__(self) -> None:
        # Prime the CPU baseline so the first real read isn't 0.0
        psutil.cpu_percent()
        self.disk_sampler = UniversalDiskSampler()
        self.network_sampler = UniversalNetworkSampler()
    
    def get_cpu_snapshot(self) -> CpuSnapshot:
        return CpuSnapshot(usage_pct=psutil.cpu_percent())
    
    def get_memory_snapshot(self) -> MemorySnapshot:
        mem = psutil.virtual_memory()
        return MemorySnapshot(
            total_gb=round(mem.total / (1024**3), 2),
            used_gb=round(mem.used / (1024**3), 2),
            available_gb=round(mem.available / (1024**3), 2),
            used_pct=round(mem.percent, 2)
        )
    
    def get_battery_snapshot(self) -> BatterySnapshot | None:
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        
        if battery.power_plugged is True or battery.power_plugged is None:
            online = True
            status = "Full" if battery.percent == 100 else "Charging"
        else:
            online = False
            status = "Discharging"
        
        hours_left = None
        if battery.secsleft not in (-1, -2) and battery.secsleft >= 0:
            hours_left = round(battery.secsleft / 3600, 2)
        
        return BatterySnapshot(
            online=online,
            status=status,
            capacity=int(battery.percent),
            power_watts=None,       # Not available on Windows psutil
            hours_left=hours_left,
            health_percent=None     # Not available on Windows psutil
        )    

    def get_thermal_snapshot(self) -> ThermalSnapshot:
        return ThermalSnapshot(
            gpu_available=False, 
            sensor_available=False,
            sensor_error="Thermal sensors not supported on this platform."
        )

    def get_disk_io_snapshot(self) -> list[DiskIOSnapshot]:
        return self.disk_sampler.get_io_snapshot()

    def get_disk_space_snapshot(self) -> DiskSpaceSnapshot:
        return self.disk_sampler.get_space_snapshot()
    
    def get_network_snapshot(self) -> list[NetworkSnapshot]:
        return self.network_sampler.get_network_snapshot()
    
    def get_system_health(self) -> dict[str, str | None]:
        return {"cpu": None, "memory": None, "battery": None, "thermal": None, "disk": None, "network": None}