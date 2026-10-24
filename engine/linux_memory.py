from dataclasses import dataclass
import os
import time

@dataclass(frozen=True)
class MemorySnapshot:
    total_gb: float
    used_gb: float
    used_pct: float
    available_gb: float
    
class LinuxMemorySampler:
    def __init__(self, mem_path: str = "/proc/meminfo"):
        self.memory_path = mem_path
    
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
            total_gb=total,
            used_gb=total - available,
            used_pct=real_used_pct,
            available_gb=available            
        )

        
    def get_mem_data(self) -> dict[str, int]:
        mem_info: dict[str, int] = {}
        
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
        
        return mem_info