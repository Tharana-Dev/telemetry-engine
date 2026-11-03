import re
import time
import shutil
from engine.models import DiskIOSnapshot, DiskSpaceSnapshot
from engine.results_and_errors import Errors, InternalResult

DEVICE_PATTERN = re.compile(
    r'^(?:sd[a-z]+|hd[a-z]+|vd[a-z]+|nvme\d+n\d+|mmcblk\d+|xv[a-z]+)$'
)


class LinuxDiskSampler:
    def __init__(self, diskstats_path: str = '/proc/diskstats') -> None:
        self.diskstats_path = diskstats_path
        self.root_path = '/'
        self._last_stats = None
        self._last_time = None
        self._last_error: Errors | None = None
        self._is_ready = False

    @property
    def last_error(self) -> Errors | None:
        return self._last_error

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def has_known_devices(self) -> bool:
        return bool(self._last_stats)

    @property
    def is_primed(self) -> bool:
        """True once at least one snapshot has been taken (baseline stored).

        Different from is_ready:
          - is_primed becomes True after the FIRST tick (baseline exists)
          - is_ready  becomes True after the SECOND tick (first real delta)

        main.py uses is_ready (so the first tick shows 'Initializing' rather
        than 'Idle'). Tests use is_primed to assert the sampler has ticked.
        """
        return self._last_stats is not None

    def _get_disk_stats(self) -> InternalResult:
        stats: dict[str, dict[str, int]] = {}
        try:
            with open(self.diskstats_path, 'r') as f:
                for line in f:
                    fields = line.split()
                    if len(fields) < 14:
                        continue
                    dev_name = fields[2]
                    if not DEVICE_PATTERN.match(dev_name):
                        continue
                    stats[dev_name] = {
                        "read": int(fields[5]),
                        "write": int(fields[9]),
                    }
            if not stats:
                return InternalResult(error=Errors.NOT_PRESENT)
            return InternalResult(data=stats)
        except FileNotFoundError:
            return InternalResult(error=Errors.FILE_NOT_FOUND)
        except PermissionError:
            return InternalResult(error=Errors.PERMISSION_DENIED)
        except (ValueError, IndexError):
            return InternalResult(error=Errors.PARSE_FAILED)
        except Exception:
            return InternalResult(error=Errors.UNKNOWN)

    def get_io_snapshot(self) -> list[DiskIOSnapshot]:
        current_time = time.monotonic()
        result = self._get_disk_stats()

        if result.error == Errors.NOT_PRESENT:
            current_stats: dict = {}
            self._last_error = None
        elif result.error:
            self._last_error = result.error
            return []
        else:
            current_stats = result.data or {}
            self._last_error = None

        if self._last_stats is None or self._last_time is None:
            self._last_stats = current_stats
            self._last_time = current_time
            return []

        self._is_ready = True

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
            read_mb_s = (read_delta * 512) / (1024 * 1024) / duration
            write_mb_s = (write_delta * 512) / (1024 * 1024) / duration
            snapshots.append(DiskIOSnapshot(
                device=dev,
                read_mib=round(read_mb_s, 2),
                write_mib=round(write_mb_s, 2),
            ))

        if current_stats:
            self._last_stats = current_stats
            self._last_time = current_time

        return snapshots

    def get_space_snapshot(self) -> DiskSpaceSnapshot:
        try:
            usage = shutil.disk_usage(self.root_path)
            return DiskSpaceSnapshot(
                total_gb=round(usage.total / (1024**3), 2),
                used_gb=round(usage.used / (1024**3), 2),
                free_gb=round(usage.free / (1024**3), 2),
                percent=round(usage.used / usage.total * 100, 1),
            )
        except Exception:
            return DiskSpaceSnapshot(
                total_gb=0.0, used_gb=0.0, free_gb=0.0, percent=0.0,
            )