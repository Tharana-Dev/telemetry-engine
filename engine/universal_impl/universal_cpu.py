import psutil
from engine.models import CpuSnapshot

class UniversalCpuSampler:
    def __init__(self) -> None:
        # Prime the internal baseline so the first reading isn't a fake 0.0
        psutil.cpu_percent(interval=None)

    def get_snapshot(self) -> CpuSnapshot:
        # Call psutil.cpu_percent() again to get the actual usage percentage
        usage = psutil.cpu_percent(interval=None)
        return CpuSnapshot(usage_pct=usage)
