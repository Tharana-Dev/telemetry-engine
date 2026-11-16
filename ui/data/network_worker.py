import threading
import time
from collections import deque
from ui.models.worker_return_models import NetworkWorkerSnapshot
from PySide6.QtCore import QObject, Signal
from ui.models.get_sampler import get_sampler
from engine.logger import logger

class NetworkWorker(QObject):
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
        self._data.get_network_snapshot()
        time.sleep(0.1)

        while not self._stop_event.is_set():
            net_list = self._data.get_network_snapshot()
            
            active_net = None
            if net_list:
                connected_nets = [n for n in net_list if n.status == "CONNECTED"]
                
                if connected_nets:
                    active_net = max(connected_nets, key=lambda x: (x.download_bps or 0) + (x.upload_bps or 0))
                else:
                    active_net = net_list[0]

            down_bps = (active_net.download_bps * 8) if active_net and active_net.download_bps is not None else None
            up_bps = (active_net.upload_bps * 8) if active_net and active_net.upload_bps is not None else None

            worker_snap = NetworkWorkerSnapshot(
                interface=active_net.interface if active_net else None,
                status=active_net.status if active_net else None,
                download_bps=down_bps,
                upload_bps=up_bps,
                rx_errors=active_net.rx_errors if active_net else None,
                tx_errors=active_net.tx_errors if active_net else None,
                rx_drops=active_net.rx_drops if active_net else None,
                tx_drops=active_net.tx_drops if active_net else None,
                total_bytes=active_net.total_bytes if active_net else None
            )

            self._data_queue.append(worker_snap)
            time.sleep(0.1)

        self.finished.emit()

    def drain_pending_snapshots(self) -> list[NetworkWorkerSnapshot]:
        pending = []
        while self._data_queue:
            pending.append(self._data_queue.popleft())

        return pending