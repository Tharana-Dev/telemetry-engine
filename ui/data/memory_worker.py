import threading
import time
from collections import deque
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal
import platform
from engine.logger import logger

def get_sampler():
    if platform.system() == "Windows":
        from engine.universal_sampler import PsutilCollector
        return PsutilCollector()
    else:
        from engine.linux_sampler import LinuxCollector
        return LinuxCollector()

@dataclass(frozen=True)
class MemoryWorkerSnapshot:
    total_gb: float | None
    used_gb: float | None
    used_pct: float | None
    available_gb: float | None

class MemoryWorker(QObject):
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
        self._data.get_memory_snapshot()
        time.sleep(0.1)

        while not self._stop_event.is_set():
            memory = self._data.get_memory_snapshot()

            worker_snap = MemoryWorkerSnapshot(
                total_gb=memory.total_gb if (memory and memory.total_gb is not None) else None,
                used_gb=memory.used_gb if (memory and memory.used_gb is not None) else None,
                used_pct=memory.used_pct if (memory and memory.used_pct is not None) else None,
                available_gb=memory.available_gb if (memory and memory.available_gb is not None) else None
            )

            self._data_queue.append(worker_snap)
            time.sleep(0.1)

        self.finished.emit()

    def drain_pending_snapshots(self) -> list[MemoryWorkerSnapshot]:
        pending = []
        while self._data_queue:
            pending.append(self._data_queue.popleft())

        return pending