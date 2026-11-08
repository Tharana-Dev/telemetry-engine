import os
import time
import psutil

from engine.models import DiskIOSnapshot, DiskSpaceSnapshot

class UniversalDiskSampler:
    def __init__(self) -> None:
        self.root_path = os.path.abspath(os.sep)
        self._last_io_stats = None
        self._last_time: float | None = None
    
    def get_space_snapshot(self) -> DiskSpaceSnapshot:
        try:
            usage = psutil.disk_usage(self.root_path)
            return DiskSpaceSnapshot(
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent=round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0,
            )
        except (FileNotFoundError, PermissionError):
            return DiskSpaceSnapshot(
                total_bytes=None,
                used_bytes=None,
                free_bytes=None,
                percent=None
            )
    
    def get_io_snapshot(self) -> list[DiskIOSnapshot]:
        current_time = time.monotonic()
        
        try:
            current_stats = psutil.disk_io_counters(perdisk=True)
        except Exception:
            return []

        if self._last_io_stats is None:
            self._last_io_stats = current_stats
            self._last_time = current_time
            return []

        duration = current_time - self._last_time
        snapshots = []

        if duration <= 0:
            return []

        for name, current in current_stats.items():
            if name not in self._last_io_stats:
                continue
                
            previous = self._last_io_stats[name]

            read_delta = current.read_bytes - previous.read_bytes
            write_delta = current.write_bytes - previous.write_bytes

            if read_delta < 0 or write_delta < 0:
                self._last_io_stats = current_stats
                self._last_time = current_time
                return []

            read_bps = read_delta / duration
            write_bps = write_delta / duration

            snapshots.append(DiskIOSnapshot(
                device=name,
                read_bps=read_bps,
                write_bps=write_bps
            ))

        self._last_io_stats = current_stats
        self._last_time = current_time

        return snapshots
