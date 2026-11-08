from engine.models import BatterySnapshot
import psutil

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

class UniversalBatterySampler:
    def __init__(self):
        self._health_percent = None
        if HAS_WMI:
            try:
                # Target the root\wmi namespace instead of the default root\cimv2
                c = wmi.WMI(namespace="root\\wmi")
                
                static_data = c.BatteryStaticData()
                full_charge_data = c.BatteryFullChargedCapacity()
                
                if static_data and full_charge_data:
                    # Match the first available battery instance
                    design = static_data[0].DesignedCapacity
                    full = full_charge_data[0].FullChargedCapacity
                    
                    if design and full and int(design) > 0:
                        self._health_percent = min(round((int(full) / int(design)) * 100, 1), 100.0)
            except Exception:
                self._health_percent = None

    def get_snapshot(self) -> BatterySnapshot | None:
        battery = psutil.sensors_battery()
        if battery is None:
            return None
            
        if battery.power_plugged is True or battery.power_plugged is None:
            online = True
            status = "Full" if battery.percent == 100 else "Charging"
        else:
            online = False
            status = "Discharging"
            
        hours_left = None
        if battery.secsleft not in (-1, -2) and battery.secsleft >= 0:
            hours_left = round(battery.secsleft / 3600, 2)
            
        return BatterySnapshot(
            online=online,
            status=status,
            capacity=int(battery.percent),
            power_watts=None,       # Not natively available on Windows
            hours_left=hours_left,
            health_percent=self._health_percent # <-- The corrected WMI Cached Health
        )
