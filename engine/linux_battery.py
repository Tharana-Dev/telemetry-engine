from engine.models import BatterySnapshot
import os

class LinuxBatterySampler:
    def __init__(self) -> None:
        self.main_path = '/sys/class/power_supply/'
        
        bat_folders = [f for f in os.listdir(self.main_path) if f.startswith('BAT')]
        ac_folders = [f for f in os.listdir(self.main_path) if f.startswith('AC')]
        
        battery_folder = bat_folders[0]
        ac_folder = ac_folders[0]
        
        self.battery_path = os.path.join(self.main_path, battery_folder)
        self.ac_path = os.path.join(self.main_path, ac_folder)

        if not bat_folders or not ac_folders:
            self.battery_path = None
            self.ac_path = None
        else:
            self.battery_path = os.path.join(self.main_path, bat_folders[0])
            self.ac_path = os.path.join(self.main_path, ac_folders[0])
    
    def get_battery_snapshot(self) -> BatterySnapshot | None:
        if self.battery_path is  None or  self.ac_path is  None:
            return None
        with open(os.path.join(self.ac_path, "online"), 'r', encoding='utf-8') as f:
            online = f.read().strip() == "1"
            
        with open(os.path.join(self.battery_path, "status"), 'r', encoding='utf-8') as f:
            status = f.read().strip()
            
        with open(os.path.join(self.battery_path, "capacity"), 'r', encoding='utf-8') as f:
            capacity = int(f.read().strip())
            
        with open(os.path.join(self.battery_path, "power_now"), "r") as f:
            power_watts = int(f.read().strip()) / 1_000_000
            
        with open(os.path.join(self.battery_path, "energy_now"), "r") as f:
            energy_now = int(f.read().strip()) / 1_000_000
            
        hours_left = round(energy_now/ power_watts, 2) if power_watts > 0 and not online else 0.0
            
        with open(os.path.join(self.battery_path, "energy_full"), "r") as f:
            efull = int(f.read().strip())
        with open(os.path.join(self.battery_path, "energy_full_design"), "r") as f:
            edesign = int(f.read().strip())
            
        health_percent = round((efull / edesign) * 100, 1) if edesign > 0 else 100.0

        return BatterySnapshot(
            online=online,
            status=status,
            capacity=capacity,
            power_watts=power_watts,
            hours_left=hours_left,
            health_percent=health_percent
            )