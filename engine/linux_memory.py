from engine.models import MemorySnapshot
import os
import time

class LinuxMemorySampler:
    def __init__(self, mem_path: str = "/proc/meminfo"):
        self.memory_path = mem_path
        with open(self.memory_path, "r", encoding='utf-8') as f:
            f.readline()
    
    def get_snapshot(self) -> MemorySnapshot:
        mem = self.get_mem_data()
        
        mem_total = mem.get("MemTotal", 0)
        mem_available = mem.get("MemAvailable", 0)
         
        if mem_total <= 0:
            return MemorySnapshot(
                total_gb=0.0,
                used_gb=0.0,
                used_pct=0.0,
                available_gb=0.0
            )
            
        total = mem_total / (1024 * 1024)
        available = mem_available / (1024 * 1024)
        real_used_pct = (1.0 - (available / total)) * 100
        
        return MemorySnapshot(
            total_gb=round(total,2),
            used_gb=round((total - available),2),
            used_pct=round(real_used_pct,2),
            available_gb=round(available,2)            
        )

    def get_mem_data(self) -> dict[str, int]:
        mem_info: dict[str, int] = {}
        
        try:
            with open(self.memory_path, "r", encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                parts: list = line.split(':', 1)
                if len(parts) < 2:
                    continue
                key = parts[0].strip()
                value_parts = parts[1].split()
                if value_parts:
                    mem_info[key] = int(value_parts[0])
        except (IOError, ValueError):
            # Safe runtime fallback if access changes while loop runs
            return {}
            
        return mem_info
