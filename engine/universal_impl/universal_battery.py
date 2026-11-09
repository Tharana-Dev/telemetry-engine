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
                # RESTORED: Target root\wmi for true battery health
                c = wmi.WMI(namespace="root\\wmi")
                
                static_data = c.BatteryStaticData()
                full_charge_data = c.BatteryFullChargedCapacity()
                
                if static_data and full_charge_data:
                    design = getattr(static_data[0], 'DesignedCapacity', 0)
                    full = getattr(full_charge_data[0], 'FullChargedCapacity', 0)
                    
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
        # FIX: Added `battery.secsleft is not None` to prevent TypeError crashes
        if battery.secsleft is not None and battery.secsleft not in (-1, -2) and battery.secsleft >= 0:
            hours_left = round(battery.secsleft / 3600, 2)
            
        return BatterySnapshot(
            online=online,
            status=status,
            capacity=int(battery.percent),
            power_watts=None,
            hours_left=hours_left,
            health_percent=self._health_percent
        )