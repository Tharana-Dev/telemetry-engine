from engine.base_sampler import BaseSystemCollector
from engine.linux_memory import LinuxMemorySampler
from engine.linux_cpu import LinuxCpuSampler

class LinuxCollector(BaseSystemCollector):
    def __init__(self) -> None:
        self.cpu_sampler = LinuxCpuSampler()
        self.mem_sampler = LinuxMemorySampler()
    
    def get_cpu_snapshot(self):
        return self.cpu_sampler.get_snapshot()
    
    def get_memory_snapshot(self):
        return self.mem_sampler.get_snapshot() 