from engine.models import (
    BatterySnapshot, CpuSnapshot, DiskIOSnapshot, MemorySnapshot, 
    NetworkSnapshot, ThermalSnapshot, DiskSpaceSnapshot
)
from engine.base_sampler import BaseSystemCollector
from engine.universal_impl.universal_disk import UniversalDiskSampler
from engine.universal_impl.universal_network import UniversalNetworkSampler
from engine.universal_impl.universal_thermal import UniversalThermalSampler
from engine.universal_impl.universal_memory import UniversalMemorySampler
from engine.universal_impl.universal_battery import UniversalBatterySampler
from engine.universal_impl.universal_cpu import UniversalCpuSampler
import psutil


class PsutilCollector(BaseSystemCollector):
    def __init__(self) -> None:
        self.cpu_sampler = UniversalCpuSampler()
        self.disk_sampler = UniversalDiskSampler()
        self.network_sampler = UniversalNetworkSampler()
        self.thermal_sampler =  UniversalThermalSampler()
        self.mem_sampler = UniversalMemorySampler()
        self.batt_sampler = UniversalBatterySampler()
         
    def get_cpu_snapshot(self):
        return self.cpu_sampler.get_snapshot()
        
    def get_memory_snapshot(self) -> MemorySnapshot:
        return self.mem_sampler.get_snapshot()

    def get_battery_snapshot(self) -> BatterySnapshot | None:
        return self.batt_sampler.get_snapshot()

    def get_thermal_snapshot(self) -> ThermalSnapshot:
        return self.thermal_sampler.get_thermal_snapshot()
    def get_disk_io_snapshot(self) -> list[DiskIOSnapshot]:
        return self.disk_sampler.get_io_snapshot()

    def get_disk_space_snapshot(self) -> DiskSpaceSnapshot:
        return self.disk_sampler.get_space_snapshot()
    
    def get_network_snapshot(self) -> list[NetworkSnapshot]:
        return self.network_sampler.get_network_snapshot()
    
    def get_system_health(self) -> dict[str, str | None]:
        return {"cpu": None, "memory": None, "battery": None, "thermal": None, "disk": None, "network": None}