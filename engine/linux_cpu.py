import psutil
from engine.models import CpuSnapshot


class LinuxCpuSampler:
    def __init__(self, stat_path: str = "/proc/stat"):
        self.stat_path = stat_path
        self._last_total: float | None = None
        self._last_idle: float | None = None
        self._initialize_first_tick()

    def _get_raw_times(self) -> tuple[float, float] | None:
        # Fatal: if /proc/stat is missing or unreadable, the open() below
        # raises FileNotFoundError / PermissionError and we let it bubble
        # up to the LinuxCollector.
        with open(self.stat_path, "r", encoding="utf-8") as f:
            line = f.readline()

        # Partial: empty file, malformed line, or missing fields -> None.
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
        # Fatal health check: /proc/stat must exist and be non-empty at
        # construction time. Explicitly bypass partial-error handling so
        # instantiation throws if the environment is restricted.
        with open(self.stat_path, "r", encoding="utf-8") as f:
            first_line = f.readline()
        if not first_line:
            raise FileNotFoundError(f"Empty stat file at {self.stat_path}")

        # Seed the baseline from a full parse. If the parse is partial
        # (e.g. malformed counters), leave the baseline unset; the first
        # good read in get_snapshot() will seed it.
        raw = self._get_raw_times()
        if raw is not None:
            self._last_total, self._last_idle = raw

    def get_snapshot(self) -> CpuSnapshot:
        # NEW: Get live frequency from psutil
        freq = psutil.cpu_freq()
        current_freq_mhz = int(freq.current) if freq else None

        raw = self._get_raw_times()

        # Partial read failure -> usage unknown, not 0.0.
        if raw is None:
            return CpuSnapshot(usage_pct=None, current_freq_mhz=current_freq_mhz)

        current_total, current_idle = raw

        # First successful read (init parse was partial) -> seed baseline
        # and report unknown usage for this tick.
        if self._last_total is None or self._last_idle is None:
            self._last_total = current_total
            self._last_idle = current_idle
            return CpuSnapshot(usage_pct=None, current_freq_mhz=current_freq_mhz)

        delta_total = current_total - self._last_total
        delta_idle = current_idle - self._last_idle

        self._last_total = current_total
        self._last_idle = current_idle

        # Clock went backwards or the file was swapped — don't divide by <= 0.
        if delta_total <= 0:
            return CpuSnapshot(usage_pct=None, current_freq_mhz=current_freq_mhz)

        usage_pct = (1.0 - (delta_idle / delta_total)) * 100

        # C1: iowait is not strictly monotonic on all kernels — it can dip
        # between reads, making delta_idle negative and driving usage_pct
        # above 100 (or below 0 if delta_idle exceeds delta_total). Clamp
        # to the physically meaningful range before rounding.
        usage_pct = max(0.0, min(100.0, usage_pct))
        return CpuSnapshot(usage_pct=round(usage_pct, 2), current_freq_mhz=current_freq_mhz)