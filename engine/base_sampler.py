from abc import ABC, abstractmethod
from engine.models import DiskSpaceSnapshot, DiskIOSnapshot, BatterySnapshot, CpuSnapshot, MemorySnapshot, ThermalSnapshot

class BaseSystemCollector(ABC):
    @abstractmethod
    def get_cpu_snapshot(self) -> CpuSnapshot:
        ...
    
    @abstractmethod
    def get_memory_snapshot(self) -> MemorySnapshot:
        ...
        
    @abstractmethod
    def get_battery_snapshot(self) -> BatterySnapshot | None:
        ...
    
    @abstractmethod
    def get_thermal_snapshot(self) -> ThermalSnapshot:
        ...

    @abstractmethod
    def get_disk_io_snapshot(self) -> list[DiskIOSnapshot]: 
        ...
    
    @abstractmethod
    def get_disk_space_snapshot(self) -> DiskSpaceSnapshot: 
        ...