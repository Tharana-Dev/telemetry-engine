from engine.base_sampler import BaseSystemCollector
from engine.linux_memory import LinuxMemorySampler
from engine.linux_cpu import LinuxCpuSampler
from engine.linux_battery import LinuxBatterySampler
from engine.linux_thermal import LinuxThermalSampler
from engine.linux_disk import LinuxDiskSampler

class LinuxCollector(BaseSystemCollector):
    def __init__(self) -> None:
        self.cpu_sampler = LinuxCpuSampler()
        self.mem_sampler = LinuxMemorySampler()
        self.battery_sampler = LinuxBatterySampler()
        self.thermal_sampler = LinuxThermalSampler()
        self.disk_sampler = LinuxDiskSampler()
    
    def get_cpu_snapshot(self):
        return self.cpu_sampler.get_snapshot()
    
    def get_memory_snapshot(self):
        return self.mem_sampler.get_snapshot() 
    
    def get_battery_snapshot(self):
        return self.battery_sampler.get_battery_snapshot()
    
    def get_thermal_snapshot(self):
        return self.thermal_sampler.get_thermal_snapshot()
    
    def get_disk_io_snapshot(self):
        return self.disk_sampler.get_io_snapshot()
        
    def get_disk_space_snapshot(self):
        return self.disk_sampler.get_space_snapshot()