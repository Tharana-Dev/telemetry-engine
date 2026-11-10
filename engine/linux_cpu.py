import psutil
from engine.models import CpuSnapshot


class LinuxCpuSampler:
    def __init__(self, stat_path: str = "/proc/stat"):
        self.stat_path = stat_path
        self._last_total: float | None = None
        self._last_idle: float | None = None
        self._initialize_first_tick()

    def _get_raw_times(self) -> tuple[float, float] | None:
        with open(self.stat_path, "r", encoding="utf-8") as f:
            line = f.readline()

        if not line:
            return None

        parts = line.split()
        try:
            cpu_times = [float(x) for x in parts[1:]]
        except ValueError:
            return None

        if len(cpu_times) < 5:
            return None

        total = sum(cpu_times[:8])
        idle = cpu_times[3] + cpu_times[4]
        return total, idle

    def _initialize_first_tick(self) -> None:
        with open(self.stat_path, "r", encoding="utf-8") as f:
            first_line = f.readline()
        if not first_line:
            raise FileNotFoundError(f"Empty stat file at {self.stat_path}")

        raw = self._get_raw_times()
        if raw is not None:
            self._last_total, self._last_idle = raw

    def get_snapshot(self) -> CpuSnapshot:
        # Get live frequency
        freq = psutil.cpu_freq()
        current_freq_mhz = int(freq.current) if freq else None

        raw = self._get_raw_times()

        if raw is None:
            return CpuSnapshot(usage_pct=None, current_freq_mhz=current_freq_mhz)

        current_total, current_idle = raw

        if self._last_total is None or self._last_idle is None:
            self._last_total = current_total
            self._last_idle = current_idle
            return CpuSnapshot(usage_pct=None, current_freq_mhz=current_freq_mhz)

        delta_total = current_total - self._last_total
        delta_idle = current_idle - self._last_idle

        self._last_total = current_total
        self._last_idle = current_idle

        if delta_total <= 0:
            return CpuSnapshot(usage_pct=None, current_freq_mhz=current_freq_mhz)

        usage_pct = (1.0 - (delta_idle / delta_total)) * 100
        usage_pct = max(0.0, min(100.0, usage_pct))
        return CpuSnapshot(usage_pct=round(usage_pct, 2), current_freq_mhz=current_freq_mhz)