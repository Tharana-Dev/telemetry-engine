from dataclasses import dataclass
from engine.models import GpuInfo

@dataclass(frozen=True)
class CpuWorkerSnapshot:
    cpu_name: str | None = None
    cpu_usage_pct: float | None = None
    cpu_freq_mhz: int | None = None # <--- Live speed
    cpu_temp: float | None = None
    cpu_vendor: str | None = "Unknown"
    cpu_base_speed_mhz: int | None = None    # <--- Base speed

@dataclass(frozen=True)
class DashboardSnapshot:
    cpu_name: str | None = None
    cpu_usage_pct: float | None = None
    cpu_freq_mhz: int | None = None
    board_vendor: str | None = None

    ram_total_gb: float | None = None
    ram_used_gb: float | None = None
    ram_used_pct: float | None = None
    
    igpu_name: str | None = None
    dgpu_name: str | None = None
    
    battery_capacity: int | None = None
    battery_status: str | None = None
    battery_online: bool | None = None
    battery_health: float | None = None
    
    disk_read_bps: float | None = None
    disk_write_bps: float | None = None
    disk_space_used_pct: float | None = None
    disk_space_free_gb: float | None = None
    
    net_status: str | None = None
    net_download_bps: float | None = None
    net_upload_bps: float | None = None

@dataclass(frozen=True)
class DiskWorkerSnapshot:
    device: str | None
    read_bps: float | None
    write_bps: float | None
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None
    percent: float | None  

@dataclass(frozen=True)
class GpuWorkerSnapshot:
    gpus: list[GpuInfo]
    is_available: bool
    igpu_name: str | None

@dataclass(frozen=True)
class MemoryWorkerSnapshot:
    total_gb: float | None
    used_gb: float | None
    used_pct: float | None
    available_gb: float | None

@dataclass(frozen=True)
class NetworkWorkerSnapshot:
    interface: str | None
    status: str | None
    download_bps: float | None
    upload_bps: float | None
    rx_errors: int | None
    tx_errors: int | None
    rx_drops: int | None
    tx_drops: int | None
    total_bytes: int | None