from engine.models import CpuSnapshot
import time
import os


class LinuxCpuSampler:
    def __init__(self, stat_path: str = "/proc/stat"):
        self.stat_path = stat_path
        self._last_total = 0.0
        self._last_idle = 0.0
        try:
            self._initialize_first_tick()
        except FileNotFoundError:
            pass  # File doesn't exist, leave as 0.0

    def _get_raw_times(self) -> tuple[float, float]:
        try:
            with open(self.stat_path, "r", encoding="utf-8") as f:
                line = f.readline()

            if not line:
                return 0.0, 0.0

            parts = line.split()
            cpu_times = [float(x) for x in parts[1:]]

            if len(cpu_times) < 5:
                return 0.0, 0.0

            total = sum(cpu_times[:8])
            idle = cpu_times[3] + cpu_times[4]

            return total, idle
        except (IOError, ValueError, IndexError):
            return 0.0, 0.0

    def _initialize_first_tick(self) -> None:
        # Early Health Check: Intentionally bypass the internal catch blocks
        # so instantiation explicitly throws if the environment is restricted.
        with open(self.stat_path, "r", encoding="utf-8") as f:
            first_line = f.readline()
            if not first_line:
                raise FileNotFoundError(f"Empty stat file at {self.stat_path}")

        # If the file verification passes, seed the primary parameters
        self._last_total, self._last_idle = self._get_raw_times()

    def get_snapshot(self) -> CpuSnapshot:
        current_total, current_idle = self._get_raw_times()

        # (0, 0) is _get_raw_times' sentinel for a failed read.
        # Return early without touching the baseline — the next good read
        # will compute its delta against the last *good* value, not against 0.
        if current_total <= 0:
            return CpuSnapshot(usage_pct=0.0)

        # First successful read (e.g. __init__ hit FileNotFoundError, so the
        # baseline was never seeded). Seed it now and report 0% for this tick.
        if self._last_total <= 0:
            self._last_total = current_total
            self._last_idle = current_idle
            return CpuSnapshot(usage_pct=0.0)

        delta_total = current_total - self._last_total
        delta_idle = current_idle - self._last_idle

        self._last_total = current_total
        self._last_idle = current_idle

        # Clock went backwards or the file was swapped — don't divide by <= 0.
        if delta_total <= 0:
            return CpuSnapshot(usage_pct=0.0)

        usage_pct = (1.0 - (delta_idle / delta_total)) * 100

        # C1: iowait is not strictly monotonic on all kernels — it can dip
        # between reads, making delta_idle negative and driving usage_pct
        # above 100 (or below 0 if delta_idle exceeds delta_total). Clamp
        # to the physically meaningful range before rounding.
        usage_pct = max(0.0, min(100.0, usage_pct))
        return CpuSnapshot(usage_pct=round(usage_pct, 2))