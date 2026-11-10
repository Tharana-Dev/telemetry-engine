from dataclasses import dataclass, field

@dataclass(frozen=True)
class MemorySnapshot:
    total_gb: float | None
    used_gb: float | None
    used_pct: float | None
    available_gb: float | None

@dataclass(frozen=True)
class CpuSnapshot:
    usage_pct: float | None
    current_freq_mhz: int | None = None  # <--- Live speed

@dataclass(frozen=True)
class BatterySnapshot:
    online: bool | None
    status: str | None
    capacity: int | None
    power_watts: float | None
    hours_left: float | None
    health_percent: float | None

@dataclass(frozen=True)
class GpuInfo:
    index: int | None
    name: str | None
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
    cpu_name: str | None = None
    cpu_base_speed_mhz: int | None = None    # <--- Base speed
    board_vendor: str | None = "Unknown"
    igpu_name: str | None = None
    gpu_error: str | None = None
    sensor_error: str | None = None
    gpu_usage: int | None = None
    gpu_power_watts: float | None = None
    gpus: list[GpuInfo] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.gpus and (self.gpu_temp is None and self.gpu_fan is None):
            first_gpu = self.gpus[0]
            object.__setattr__(self, "gpu_temp", first_gpu.temperature_c)
            object.__setattr__(self, "gpu_fan", first_gpu.fan_speed_pct)
            object.__setattr__(self, "gpu_usage", first_gpu.utilization_pct)
            object.__setattr__(self, "gpu_power_watts", first_gpu.power_w)

@dataclass(frozen=True)
class DiskIOSnapshot:
    device: str | None
    read_bps: float | None
    write_bps: float | None

@dataclass(frozen=True)
class DiskSpaceSnapshot:
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None
    percent: float | None        

@dataclass(frozen=True)
class NetworkSnapshot:
    interface: str | None
    status: str | None
    download_bps: float | None
    upload_bps: float | None
    rx_errors: int | None
    tx_errors: int | None
    rx_drops: int | None
    tx_drops: int | None
    total_bytes: int | None