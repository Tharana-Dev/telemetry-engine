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
