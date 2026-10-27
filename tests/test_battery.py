import pytest
from engine.linux_battery import LinuxBatterySampler 
from engine.models import BatterySnapshot

def _write(path, value):
    """Helper: write a sysfs-style single-value file."""
    path.write_text(str(value))

def test_battery_sampler_happy_path(tmp_path):
    fake_bat = tmp_path / "BAT0"
    fake_bat.mkdir()
    fake_ac = tmp_path / "AC"
    fake_ac.mkdir()
    
    _write(fake_bat / "capacity", "85")
    _write(fake_bat / "status", "Discharging")
    _write(fake_bat / "power_now", "10000000")          # µW -> 10 W
    _write(fake_bat / "energy_now", "50000000")         # µWh
    _write(fake_bat / "energy_full", "50000000")        # µWh
    _write(fake_bat / "energy_full_design", "60000000") # µWh
    _write(fake_ac / "online", "0")
    
    sampler = LinuxBatterySampler(sys_path=str(tmp_path))
    snapshot = sampler.get_battery_snapshot()

    assert snapshot is not None
    assert snapshot.capacity == 85
    assert snapshot.online is False
    assert snapshot.power_watts == pytest.approx(10.0)
    assert snapshot.health_percent == pytest.approx(83.3, abs=0.1)
    assert snapshot.status == "Discharging"


def test_linux_desktop_fallback_no_battery(tmp_path):
    """Only an AC adapter exists (e.g. a desktop) -> no snapshot."""
    (tmp_path / "AC").mkdir()
    _write(tmp_path / "AC" / "online", "1")

    sampler = LinuxBatterySampler(sys_path=str(tmp_path))
    assert sampler.get_battery_snapshot() is None


def test_linux_desktop_fallback_empty_dir(tmp_path):
    """No power_supply entries at all -> no snapshot."""
    sampler = LinuxBatterySampler(sys_path=str(tmp_path))
    assert sampler.get_battery_snapshot() is None    
    
    
    