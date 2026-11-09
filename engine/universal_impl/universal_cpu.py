import psutil
from engine.models import CpuSnapshot

class UniversalCpuSampler:
    def __init__(self) -> None:
        # Prime the internal baseline so the first reading isn't a fake 0.0
        psutil.cpu_percent(interval=None)

    def get_snapshot(self) -> CpuSnapshot:
        # Get live usage percentage
        usage = psutil.cpu_percent(interval=None)
        
        # Get live frequency
        freq = psutil.cpu_freq()
        current_mhz = int(freq.current) if freq else None
        
        return CpuSnapshot(
            usage_pct=usage,
            current_freq_mhz=current_mhz
        )