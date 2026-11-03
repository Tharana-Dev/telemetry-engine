from dataclasses import dataclass, field
from typing import Any
from enum import Enum

@dataclass(frozen=True)
class MemorySnapshot:
    total_gb: float
    used_gb: float
    used_pct: float
    available_gb: float

@dataclass(frozen=True)
class CpuSnapshot:
    usage_pct: float
    
@dataclass(frozen=True)
class BatterySnapshot:
    # 1. Main Status & Core Metrics
    online: bool                       # From AC1/online (True if wall power is connected)
    status: str                        # From BAT1/status ('Charging', 'Discharging', 'Full', 'N/A')
    capacity: int | None               # From BAT1/capacity (0-100% fuel gauge); None if missing

    # 2. Live Power Dynamics
    power_watts: float | None          # Calculated from BAT1/power_now (divided by 1,000,000)
    hours_left: float | None           # Calculated from BAT1/energy_now / BAT1/power_now
    health_percent: float | None       # Calculated from (energy_full / energy_full_design) * 100

@dataclass(frozen=True)
class GpuInfo:
    index: int
    name: str
    temperature_c: float | None
    utilization_pct: int | None
    power_w: float | None
    fan_speed_pct: int | None

@dataclass(frozen=True)
class ThermalSnapshot:
    cpu_temp: float | None = None
    cpu_temp_max: float | None = None
    gpu_temp: float | None = None
    gpu_fan: int | None = None
    system_fans: dict[str, int] | None = None
    gpu_available: bool = True
    sensor_available: bool = True
    cpu_vendor: str | None = "Unknown"
    board_vendor: str | None = "Unknown"
    gpu_error: str | None = None
    sensor_error: str | None = None
    gpu_usage: int | None = None
    gpu_power_watts: float | None = None
    gpus: list[GpuInfo] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Automatically fills legacy properties from the first GPU if not set."""
        if self.gpus and (self.gpu_temp is None and self.gpu_fan is None):
            first_gpu = self.gpus[0]
            object.__setattr__(self, "gpu_temp", first_gpu.temperature_c)
            object.__setattr__(self, "gpu_fan", first_gpu.fan_speed_pct)
            object.__setattr__(self, "gpu_usage", first_gpu.utilization_pct)
            object.__setattr__(self, "gpu_power_watts", first_gpu.power_w)


@dataclass(frozen=True)
class DiskIOSnapshot:
    device: str
    read_mbps: float
    write_mbps: float

@dataclass(frozen=True)
class DiskSpaceSnapshot:
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float            

@dataclass(frozen=True)
class NetworkSnapshot:
    interface: str
    status: str
    download_bps: float
    upload_bps: float
    rx_errors: int
    tx_errors: int
    rx_drops: int
    tx_drops: int
    total_bytes: float