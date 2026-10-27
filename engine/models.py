from dataclasses import dataclass

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
    capacity: int                      # From BAT1/capacity (0-100% fuel gauge)
    
    # 2. Live Power Dynamics
    power_watts: float                 # Calculated from BAT1/power_now (divided by 1,000,000)
    hours_left: float      # Calculated from BAT1/energy_now / BAT1/power_now
    health_percent: float    # Calculated from (BAT1/energy_full / BAT1/energy_full_design) * 100
