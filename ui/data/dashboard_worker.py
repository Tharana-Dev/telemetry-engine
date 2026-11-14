import threading
import time
from collections import deque
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal
import platform
from engine.logger import logger

@dataclass(frozen=True)
class DashboardSnapshot:
    cpu_name: str | None = None
    cpu_usage_pct: float | None = None
    cpu_freq_mhz: int | None = None
    ram_total_gb: float | None = None
    ram_used_gb: float | None = None
    ram_used_pct: float | None = None
    igpu_name: str | None = None
    dgpu_name: str | None = None
    battery_capacity: int | None = None
    battery_status: str | None = None
    disk_read_bps: float | None = None
    disk_write_bps: float | None = None
    disk_space_used_pct: float | None = None
    disk_space_free_gb: float | None = None
    net_status: str | None = None
    net_download_bps: float | None = None
    net_upload_bps: float | None = None

def get_sampler():
    if platform.system() == "Windows":
        from engine.universal_sampler import PsutilCollector
        return PsutilCollector()
    else:
        from engine.linux_sampler import LinuxCollector
        return LinuxCollector()

class DashboardDataCollector(QObject):
    finished = Signal()
    
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._data_queue = deque(maxlen=100)
        
        try:
            self._data = get_sampler()
        except Exception as e:
            logger.error(f"Failed to initialize collector: {e}")
            self._data = None

    def work(self):
        if self._data is None:
            self.finished.emit()
            return

        time.sleep(2.0) # Startup spike wait

        self._data.get_cpu_snapshot()
        self._data.get_disk_io_snapshot()
        self._data.get_network_snapshot()
        self._data.get_battery_snapshot()
        self._data.get_disk_space_snapshot()
        self._data.get_thermal_snapshot()
        time.sleep(0.1)

        while not self._stop_event.is_set():
            cpu = self._data.get_cpu_snapshot()
            mem = self._data.get_memory_snapshot()
            disk_io_list = self._data.get_disk_io_snapshot()
            net_list = self._data.get_network_snapshot()
            thermal = self._data.get_thermal_snapshot()
            battery = self._data.get_battery_snapshot()
            disk_space = self._data.get_disk_space_snapshot()

            # Extract data
            cpu_name = thermal.cpu_name if thermal else None
            cpu_usage = cpu.usage_pct if cpu else None
            cpu_freq = cpu.current_freq_mhz if cpu else None
            ram_total = mem.total_gb if mem else None
            ram_used = mem.used_gb if mem else None
            ram_pct = mem.used_pct if mem else None
            igpu = thermal.igpu_name if thermal else None
            dgpu = thermal.gpus[0].name if thermal and thermal.gpus else None
            batt_cap = battery.capacity if battery else None
            batt_status = battery.status if battery else None
            
            # Disk I/O (Sum all disks to get total system I/O)
            d_read = 0.0
            d_write = 0.0
            if disk_io_list:
                for d in disk_io_list:
                    if d.read_bps:
                        d_read += d.read_bps
                    if d.write_bps:
                        d_write += d.write_bps
                
            # Disk Space
            d_used_pct = disk_space.percent if disk_space else None
            d_free_gb = (disk_space.free_bytes / (1024**3)) if disk_space and disk_space.free_bytes else None
            
            # Network (Find the active connection with the most traffic)
            n_status = None
            n_down = None
            n_up = None
            if net_list:
                # Look for the interface with the highest traffic. 
                # This will naturally skip disconnected adapters (which have 0 traffic).
                active_net = max(net_list, key=lambda x: (x.download_bps or 0) + (x.upload_bps or 0))
                n_status = active_net.status
                n_down = active_net.download_bps
                n_up = active_net.upload_bps

            dashboard = DashboardSnapshot(
                cpu_name=cpu_name, cpu_usage_pct=cpu_usage, cpu_freq_mhz=cpu_freq,
                ram_total_gb=ram_total, ram_used_gb=ram_used, ram_used_pct=ram_pct,
                igpu_name=igpu, dgpu_name=dgpu,
                battery_capacity=batt_cap, battery_status=batt_status,
                disk_read_bps=d_read, disk_write_bps=d_write, 
                disk_space_used_pct=d_used_pct, disk_space_free_gb=d_free_gb,
                net_status=n_status, net_download_bps=n_down, net_upload_bps=n_up
            )

            self._data_queue.append(dashboard)
            time.sleep(0.1)

        self.finished.emit()

    def drain_pending_snapshots(self) -> list[DashboardSnapshot]:
        """Called by the UI Timer. Empties the deque and returns all snapshots."""
        pending = []
        while self._data_queue:
            pending.append(self._data_queue.popleft())
        return pending
