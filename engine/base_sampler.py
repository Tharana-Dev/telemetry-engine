from abc import ABC, abstractmethod
from engine.models import CpuSnapshot, MemorySnapshot

class BaseSystemCollector(ABC):
    @abstractmethod
    def get_cpu_snapshot(self) -> CpuSnapshot:
        ...
    
    @abstractmethod
    def get_memory_snapshot(self) -> MemorySnapshot:
        ...
        
