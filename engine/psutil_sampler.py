from engine.models import CpuSnapshot, MemorySnapshot
from engine.linux_sampler import BaseSystemCollector
import psutil

class PsutilCollector(BaseSystemCollector):
    def __init__(self) -> None:
        ...
    
    def get_cpu_snapshot(self) -> CpuSnapshot:
        return CpuSnapshot(
            usage_pct= psutil.cpu_percent()
        )
    
    def get_memory_snapshot(self) -> MemorySnapshot:
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024**3), 2)
        used_gb = round(mem.used / (1024**3), 2)
        available_gb = round(mem.available / (1024**3), 2)
        used_pct = round(mem.percent, 2)  # psutil already gives this as a percentage float
        
        return MemorySnapshot(
            total_gb=total_gb,
            used_gb=used_gb,
            used_pct=used_pct,
            available_gb=available_gb
    )