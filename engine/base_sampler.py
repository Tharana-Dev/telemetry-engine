from abc import ABC, abstractmethod
from engine.models import BatterySnapshot, CpuSnapshot, MemorySnapshot

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