import threading
import time
from collections import deque
from ui.models.worker_return_models import DiskWorkerSnapshot
from PySide6.QtCore import QObject, Signal
from ui.models.get_sampler import get_sampler
from engine.logger import logger

class DiskWorker(QObject):
    finished = Signal()

    def __init__(self):
        super().__init__()
        
        self._stop_event = threading.Event()
        self._data_queue = deque(maxlen=600)

        try:
            self._data = get_sampler()
        except Exception as e:
            logger.error(f"Failed to initialize collector: {e}")
            self._data = None

    def work(self):
        if self._data is None:
            self.finished.emit()
            return

        # Prime the baselines
        time.sleep(1.0)
        self._data.get_disk_io_snapshot()
        self._data.get_disk_space_snapshot()
        time.sleep(0.1)

        while not self._stop_event.is_set():
            disk_io_list = self._data.get_disk_io_snapshot()
            disk_space = self._data.get_disk_space_snapshot()

            total_read = 0.0
            total_write = 0.0
            primary_device = "All Drives"
            
            if disk_io_list:
                primary_device = disk_io_list[0].device
                for d in disk_io_list:
                    if d.read_bps: total_read += d.read_bps
                    if d.write_bps: total_write += d.write_bps

            total_b = disk_space.total_bytes if disk_space else None
            used_b = disk_space.used_bytes if disk_space else None
            free_b = disk_space.free_bytes if disk_space else None
            pct = disk_space.percent if disk_space else None
            
            worker_snap = DiskWorkerSnapshot(
                device=primary_device,
                read_bps=total_read if disk_io_list else None,
                write_bps=total_write if disk_io_list else None,
                total_bytes=total_b,
                used_bytes=used_b,
                free_bytes=free_b,
                percent=pct
            )

            self._data_queue.append(worker_snap)
            time.sleep(0.1)

        self.finished.emit()

    def drain_pending_snapshots(self) -> list[DiskWorkerSnapshot]:
        pending = []
        while self._data_queue:
            pending.append(self._data_queue.popleft())
        return pending