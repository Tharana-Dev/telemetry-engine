import psutil
from engine.models import MemorySnapshot

class UniversalMemorySampler:
    def get_snapshot(self) -> MemorySnapshot:
        mem = psutil.virtual_memory()
        return MemorySnapshot(
            total_gb=round(mem.total / (1024**3), 2),
            used_gb=round(mem.used / (1024**3), 2),
            available_gb=round(mem.available / (1024**3), 2),
            used_pct=round(mem.percent, 2)
        )