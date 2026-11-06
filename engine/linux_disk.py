import re
import time
import shutil
from engine.models import DiskIOSnapshot, DiskSpaceSnapshot

DEVICE_PATTERN = re.compile(
    r'^(?:sd[a-z]+|hd[a-z]+|vd[a-z]+|nvme\d+n\d+|mmcblk\d+|xv[a-z]+)$'
)


class LinuxDiskSampler:
    def __init__(self, diskstats_path: str = '/proc/diskstats') -> None:
        self.diskstats_path = diskstats_path
        self.root_path = '/'
        self._last_stats: dict[str, dict[str, int]] | None = None
        self._last_time: float | None = None

    def _get_disk_stats(self) -> dict[str, dict[str, int]]:
        stats: dict[str, dict[str, int]] = {}
        with open(self.diskstats_path, 'r') as f:
            for line in f:
                fields = line.split()
                # Partial: malformed line -> skip, keep going.
                if len(fields) < 14:
                    continue
                dev_name = fields[2]
                if not DEVICE_PATTERN.match(dev_name):
                    continue
                try:
                    stats[dev_name] = {
                        "read": int(fields[5]),
                        "write": int(fields[9]),
                    }
                except ValueError:
                    # Partial: non-numeric field -> skip this device, keep going.
                    continue
        # No matching devices -> empty dict. get_io_snapshot turns that into
        # an empty list (no hardware / nothing to report).
        return stats

    def get_io_snapshot(self) -> list[DiskIOSnapshot] | None:
        current_time = time.monotonic()
        current_stats = self._get_disk_stats()

        # First tick: seed the baseline, report nothing yet.
        if self._last_stats is None or self._last_time is None:
            self._last_stats = current_stats
            self._last_time = current_time
            return []
        
        if not current_stats:
            return None
        
        duration = current_time - self._last_time
        if duration <= 0:
            duration = 1.0

        snapshots: list[DiskIOSnapshot] = []
        for dev, data2 in current_stats.items():
            data1 = self._last_stats.get(dev)
            if data1 is None:
                continue
            read_delta = max(0, data2["read"] - data1["read"])
            write_delta = max(0, data2["write"] - data1["write"])
            # Raw bytes/sec — no MiB conversion here. The view formats.
            read_bps = (read_delta * 512) / duration
            write_bps = (write_delta * 512) / duration
            snapshots.append(DiskIOSnapshot(
                device=dev,
                read_bps=read_bps,
                write_bps=write_bps,
            ))

        if current_stats:
            self._last_stats = current_stats
            self._last_time = current_time

        return snapshots

    def get_space_snapshot(self) -> DiskSpaceSnapshot:
        # Fatal: if the root filesystem can't be stat'd, shutil.disk_usage
        # raises FileNotFoundError / PermissionError and we let it bubble.
        usage = shutil.disk_usage(self.root_path)
        return DiskSpaceSnapshot(
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            percent=round(usage.used / usage.total * 100, 1) if usage.total > 0 else None,
        )