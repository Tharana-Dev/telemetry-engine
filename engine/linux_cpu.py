from dataclasses import dataclass
import time
import os

@dataclass(frozen=True)
class CpuSnapshot:
    usage_pct: float

class LinuxCpuSampler:
    def __init__(self, stat_path: str = "/proc/stat"):
        self.stat_path = stat_path
        self._last_total = 0.0
        self._last_idle = 0.0
        self._initialize_first_tick()

    def _get_raw_times(self) -> tuple[float, float]:
        try:
            with open(self.stat_path, "r", encoding="utf-8") as f:
                line = f.readline()
            
            if not line:
                return 0.0, 0.0
                
            parts = line.split()
            cpu_times = [float(x) for x in parts[1:]]
            
            # Guard check: Ensure we have enough columns for idle (index 3) and iowait (index 4)
            if len(cpu_times) < 5:
                return 0.0, 0.0
                
            total = sum(cpu_times)
            idle = cpu_times[3] + cpu_times[4]
            
            return total, idle
        except (IOError, ValueError, IndexError):
            # Gracefully fall back to zero states if file errors, value conversion issues, or bounds exceptions occur
            return 0.0, 0.0

    def _initialize_first_tick(self) -> None:
        self._last_total, self._last_idle = self._get_raw_times()

    def get_snapshot(self) -> CpuSnapshot:
        current_total, current_idle = self._get_raw_times()
        
        delta_total = current_total - self._last_total
        delta_idle = current_idle - self._last_idle
        
        self._last_total = current_total
        self._last_idle = current_idle
        
        # Protects against zero movement or double fallback zero matching scenarios
        if delta_total <= 0:
            return CpuSnapshot(usage_pct=0.0)
            
        usage_pct = (1.0 - (delta_idle / delta_total)) * 100
        return CpuSnapshot(usage_pct=round(usage_pct, 2))
