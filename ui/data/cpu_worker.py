import threading
import time
from collections import deque

from PySide6.QtCore import QObject, Signal
from ui.models.get_sampler import get_sampler
from engine.logger import logger
from ui.models.worker_return_models import CpuWorkerSnapshot

class CpuWorker(QObject):
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
        self._data.get_cpu_snapshot()
        self._data.get_thermal_snapshot() # <---- get the cpu data from WMI WinTMP Register etc
        time.sleep(0.1)

        while not self._stop_event.is_set():
            cpu = self._data.get_cpu_snapshot()
            thermal = self._data.get_thermal_snapshot()

            cpu_usage = cpu.usage_pct if (cpu and cpu.usage_pct is not None) else None
            cpu_freq = cpu.current_freq_mhz if (cpu and cpu.current_freq_mhz is not None) else None
            
            cpu_name = thermal.cpu_name if (thermal and thermal.cpu_name) else None
            cpu_temp = thermal.cpu_temp if (thermal and thermal.cpu_temp is not None) else None
            cpu_vendor = thermal.cpu_vendor if (thermal and thermal.cpu_vendor) else None
            cpu_base_speed_mhz = thermal.cpu_base_speed_mhz if (thermal and thermal.cpu_base_speed_mhz is not None) else None

            worker_snap = CpuWorkerSnapshot(
                cpu_name=cpu_name,
                cpu_usage_pct= cpu_usage,
                cpu_freq_mhz= cpu_freq,
                cpu_temp= cpu_temp,
                cpu_vendor= cpu_vendor,
                cpu_base_speed_mhz= cpu_base_speed_mhz
            )

            self._data_queue.append(worker_snap)
            time.sleep(0.1)

        self.finished.emit()

    def drain_pending_snapshots(self) -> list[CpuWorkerSnapshot]:
        pending = []
        while self._data_queue:
            pending.append(self._data_queue.popleft())
        return pending
