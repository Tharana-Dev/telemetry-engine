import pytest
from engine.linux_cpu import LinuxCpuSampler, CpuSnapshot

def test_cpu_sampler_happy_path(tmp_path):
    """Tests perfect calculation math across two consecutive tick timelines."""
    fake_stat = tmp_path / "stat"
    
    # Tick 1: Total = 400.0, Idle = 250.0
    fake_stat.write_text("cpu  100 0 50 200 50 0 0 0 0 0\n", encoding="utf-8")
    sampler = LinuxCpuSampler(stat_path=str(fake_stat))
    
    assert sampler._last_total == 400.0
    assert sampler._last_idle == 250.0

    # Tick 2: Total = 600.0 (Delta 200), Idle = 300.0 (Delta 50)
    # Math: (1.0 - (50 / 200)) * 100 = 75.0%
    fake_stat.write_text("cpu  200 0 100 250 50 0 0 0 0 0\n", encoding="utf-8")
    snapshot = sampler.get_snapshot()
    
    assert isinstance(snapshot, CpuSnapshot)
    assert snapshot.usage_pct == 75.0


def test_cpu_sampler_zero_delta_protection(tmp_path):
    """Ensures identical tick readings output 0.0% smoothly."""
    fake_stat = tmp_path / "stat"
    tick_data = "cpu  100 0 50 200 50 0 0 0 0 0\n"
    
    fake_stat.write_text(tick_data, encoding="utf-8")
    sampler = LinuxCpuSampler(stat_path=str(fake_stat))
    snapshot = sampler.get_snapshot()
    
    assert snapshot.usage_pct == 0.0


def test_cpu_sampler_corrupt_lines_returns_zero_snapshot(tmp_path):
    """Verifies that short, incomplete rows are caught by safety logic and won't crash."""
    fake_stat = tmp_path / "stat"
    fake_stat.write_text("cpu 10 20\n", encoding="utf-8") # Missing crucial indexes
    
    sampler = LinuxCpuSampler(stat_path=str(fake_stat))
    snapshot = sampler.get_snapshot()
    
    assert snapshot.usage_pct == 0.0


def test_cpu_sampler_missing_file_fallback():
    """Verifies that a completely missing file path gracefully yields a 0.0% snapshot."""
    sampler = LinuxCpuSampler(stat_path="/nonexistent/path/to/stat")
    snapshot = sampler.get_snapshot()
    
    assert snapshot.usage_pct == 0.0
