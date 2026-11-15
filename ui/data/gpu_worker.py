import threading
import time
from collections import deque
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal
import platform
from engine.logger import logger
from engine.models import GpuInfo

def get_sampler():
    if platform.system() == "Windows":
        from engine.universal_sampler import PsutilCollector
        return PsutilCollector()
    else:
        from engine.linux_sampler import LinuxCollector
        return LinuxCollector()

@dataclass(frozen=True)
class GpuWorkerSnapshot:
    gpus: list[GpuInfo]
    is_available: bool
    igpu_name: str | None

class GpuWorker(QObject):
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

        time.sleep(1.0)
        self._data.get_thermal_snapshot()
        time.sleep(0.1)

        while not self._stop_event.is_set():
            thermal = self._data.get_thermal_snapshot()

            worker_snap = GpuWorkerSnapshot(
                gpus=thermal.gpus if thermal else [],
                is_available=thermal.gpu_available if thermal else False,
                igpu_name=thermal.igpu_name if thermal else None
            )

            self._data_queue.append(worker_snap)
            time.sleep(0.1)

        self.finished.emit()

    def drain_pending_snapshots(self) -> list[GpuWorkerSnapshot]:
        pending = []
        while self._data_queue:
            pending.append(self._data_queue.popleft())
        return pending