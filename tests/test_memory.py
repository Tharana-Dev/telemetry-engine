import os
import pytest
from engine.linux_memory import LinuxMemorySampler 
from engine.models import MemorySnapshot

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mock_meminfo.txt")

def test_memory_sampler_happy_path_and_parsing():
    sampler = LinuxMemorySampler(mem_path=FIXTURE_PATH)
    snapshot = sampler.get_snapshot()
    
    assert isinstance(snapshot, MemorySnapshot)

    assert snapshot.total_gb == 16.0
    assert snapshot.available_gb == 8.0
    assert snapshot.used_gb == 8.0
    assert snapshot.used_pct == 50.0

    raw_data = sampler.get_mem_data()
    assert "MemTotal" in raw_data
    assert "SpacedKey" in raw_data
    assert raw_data["SpacedKey"] == 1000


def test_memory_sampler_missing_keys_returns_zero_snapshot():
    """Verifies that missing keys return an empty snapshot instead of a KeyError."""
    sampler = LinuxMemorySampler(mem_path="/dev/null")
    snapshot = sampler.get_snapshot()
    
    assert snapshot.total_gb == 0.0
    assert snapshot.used_pct == 0.0


def test_memory_sampler_zero_total_memory_returns_zero_snapshot(tmp_path):
    """Verifies that zero division limits are bypassed safely."""
    zero_mem_file = tmp_path / "zero_meminfo"
    zero_mem_file.write_text(
        "MemTotal:              0 kB\n"
        "MemAvailable:          0 kB\n",
        encoding="utf-8"
    )
    
    sampler = LinuxMemorySampler(mem_path=str(zero_mem_file))
    snapshot = sampler.get_snapshot()
    
    assert snapshot.total_gb == 0.0
    assert snapshot.used_pct == 0.0
