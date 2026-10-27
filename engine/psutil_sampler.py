from engine.models import BatterySnapshot, CpuSnapshot, MemorySnapshot
from engine.linux_sampler import BaseSystemCollector

import psutil

class PsutilCollector(BaseSystemCollector):
    def __init__(self) -> None:
        ...
    
    def get_cpu_snapshot(self) -> CpuSnapshot:
        return CpuSnapshot(
            usage_pct= psutil.cpu_percent()
        )
    
    def get_memory_snapshot(self) -> MemorySnapshot:
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024**3), 2)
        used_gb = round(mem.used / (1024**3), 2)
        available_gb = round(mem.available / (1024**3), 2)
        used_pct = round(mem.percent, 2)  # psutil already gives this as a percentage float
        
        return MemorySnapshot(
            total_gb=total_gb,
            used_gb=used_gb,
            used_pct=used_pct,
            available_gb=available_gb
    )
    
    def get_battery_snapshot(self) -> BatterySnapshot | None:
        battery = psutil.sensors_battery()
        
        if battery is None:
            return BatterySnapshot(
                online=True,
                status="AC Power Only",
                capacity=100,
                power_watts=0.0,
                hours_left=0.0,
                health_percent=100.0
            )
        
        if battery.power_plugged is True or battery.power_plugged is None:
            online = True
            status = "Full" if battery.percent == 100 else "Charging"
        else:
            online = False
            status = "Discharging"
        
        hours_left = 0.0 if battery.secsleft in (-1,-2) or battery.secsleft <0 else round(battery.secsleft / 3600, 2)
        
        #FallBack
        
        power_watts = 0.0
        health_percent = 100.0
        
        return BatterySnapshot(
            online=online,
            status=status,
            capacity=int(battery.percent),
            power_watts=power_watts,
            hours_left= hours_left,
            health_percent= health_percent
        )    