import platform
import pytest
import time
from unittest.mock import patch, MagicMock

from engine.universal_impl.universal_cpu import UniversalCpuSampler
from engine.universal_impl.universal_memory import UniversalMemorySampler
from engine.universal_impl.universal_battery import UniversalBatterySampler
from engine.universal_impl.universal_thermal import UniversalThermalSampler
from engine.universal_impl.universal_disk import UniversalDiskSampler
from engine.universal_impl.universal_network import UniversalNetworkSampler

from engine.universal_sampler import PsutilCollector 

import pynvml

IS_WINDOWS = platform.system() == "Windows"


# ===========================================================================
# 1. CPU Tests (3)
# ===========================================================================

@patch("psutil.cpu_percent", return_value=45.0)
def test_universal_cpu_normal(mock_cpu):
    sampler = UniversalCpuSampler()
    snap = sampler.get_snapshot()
    assert snap.usage_pct == 45.0

@patch("psutil.cpu_percent")
def test_universal_cpu_primes_baseline(mock_cpu):
    mock_cpu.return_value = 10.0
    sampler = UniversalCpuSampler()
    assert mock_cpu.call_count == 1

@patch("engine.universal_sampler.UniversalCpuSampler.get_snapshot")
def test_universal_cpu_psutil_crash(mock_get_snapshot):
    mock_get_snapshot.side_effect = RuntimeError("psutil crash")
    collector = PsutilCollector()
    result = collector.get_cpu_snapshot()
    assert result is None


# ===========================================================================
# 2. Memory Tests (3)
# ===========================================================================

@patch("psutil.virtual_memory")
def test_universal_memory_normal(mock_vm):
    mock_vm.return_value = MagicMock(
        total=16 * 1024**3, 
        used=8 * 1024**3, 
        available=8 * 1024**3, 
        percent=50.0
    )
    sampler = UniversalMemorySampler()
    snap = sampler.get_snapshot()
    
    assert snap.total_gb == 16.0
    assert snap.used_gb == 8.0
    assert snap.used_pct == 50.0

@patch("psutil.virtual_memory")
def test_universal_memory_zero_total(mock_vm):
    mock_vm.return_value = MagicMock(total=0, used=0, available=0, percent=0)
    sampler = UniversalMemorySampler()
    snap = sampler.get_snapshot()
    
    assert snap.total_gb == 0.0
    assert snap.used_pct is None or snap.used_pct == 0.0

@patch("engine.universal_sampler.UniversalMemorySampler.get_snapshot")
def test_universal_memory_psutil_crash(mock_get_snapshot):
    mock_get_snapshot.side_effect = Exception("psutil crash")
    collector = PsutilCollector()
    result = collector.get_memory_snapshot()
    assert result is None


# ===========================================================================
# 3. Battery Tests (7)
# ===========================================================================

@patch("engine.universal_impl.universal_battery.HAS_WMI", False)
def test_universal_battery_no_wmi():
    sampler = UniversalBatterySampler()
    assert sampler._health_percent is None

@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
@patch("engine.universal_impl.universal_battery.HAS_WMI", True)
@patch("engine.universal_impl.universal_battery.wmi.WMI", side_effect=Exception("WMI crash"))
def test_universal_battery_wmi_crash(mock_wmi):
    sampler = UniversalBatterySampler()
    assert sampler._health_percent is None

@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
@patch("engine.universal_impl.universal_battery.HAS_WMI", True)
@patch("engine.universal_impl.universal_battery.wmi.WMI")
def test_universal_battery_wmi_zero_design(mock_wmi):
    mock_wmi_instance = mock_wmi.return_value
    mock_wmi_instance.BatteryStaticData.return_value = [MagicMock(DesignedCapacity=0)]
    mock_wmi_instance.BatteryFullChargedCapacity.return_value = [MagicMock(FullChargedCapacity=90)]
    
    sampler = UniversalBatterySampler()
    assert sampler._health_percent is None

@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
@patch("engine.universal_impl.universal_battery.HAS_WMI", True)
@patch("engine.universal_impl.universal_battery.wmi.WMI")
def test_universal_battery_wmi_calculation(mock_wmi):
    mock_wmi_instance = mock_wmi.return_value
    mock_wmi_instance.BatteryStaticData.return_value = [MagicMock(DesignedCapacity=100)]
    mock_wmi_instance.BatteryFullChargedCapacity.return_value = [MagicMock(FullChargedCapacity=90)]
    
    sampler = UniversalBatterySampler()
    assert sampler._health_percent == 90.0

@patch("psutil.sensors_battery", return_value=None)
def test_universal_battery_no_battery(mock_bat):
    sampler = UniversalBatterySampler()
    assert sampler.get_snapshot() is None

@patch("psutil.sensors_battery")
def test_universal_battery_charging(mock_bat):
    mock_bat.return_value = MagicMock(power_plugged=True, percent=80, secsleft=None)
    sampler = UniversalBatterySampler()
    snap = sampler.get_snapshot()
    
    assert snap.status == "Charging"
    assert snap.online is True
    assert snap.capacity == 80

@patch("psutil.sensors_battery")
def test_universal_battery_discharging(mock_bat):
    mock_bat.return_value = MagicMock(power_plugged=False, percent=50, secsleft=7200)
    sampler = UniversalBatterySampler()
    snap = sampler.get_snapshot()
    
    assert snap.status == "Discharging"
    assert snap.online is False
    assert snap.hours_left == 2.0


# ===========================================================================
# 4. Thermal Tests (6)
# ===========================================================================

@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
@patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=False, create=True)
def test_universal_thermal_no_admin(mock_admin):
    sampler = UniversalThermalSampler()
    snap = sampler.get_thermal_snapshot()
    assert "Admin privileges" in snap.sensor_error

@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
@patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=True, create=True)
@patch("builtins.__import__", side_effect=ImportError("WinTmp not found"))
def test_universal_thermal_admin_but_wintmp_fails(mock_import, mock_admin):
    sampler = UniversalThermalSampler()
    snap = sampler.get_thermal_snapshot()
    assert snap is not None
    assert snap.sensor_error is not None

@patch("pynvml.nvmlInit", side_effect=Exception("NVML missing"))
def test_universal_thermal_nvml_init_fails(mock_nvml):
    sampler = UniversalThermalSampler()
    snap = sampler.get_thermal_snapshot()
    assert snap.gpu_available is False

@patch("pynvml.nvmlInit")
@patch("pynvml.nvmlDeviceGetCount", side_effect=pynvml.NVMLError("Driver lost"))
def test_universal_thermal_nvml_lost_mid_session(mock_count, mock_init):
    sampler = UniversalThermalSampler()
    assert sampler.initialized is True 
    sampler.get_thermal_snapshot()
    assert sampler.initialized is False

@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
@patch("winreg.OpenKey", side_effect=FileNotFoundError, create=True)
def test_universal_thermal_winreg_fallback(mock_open_key):
    sampler = UniversalThermalSampler()
    snap = sampler.get_thermal_snapshot()
    assert snap.cpu_name is None

@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
@patch("engine.universal_impl.universal_thermal.wmi.WMI", side_effect=Exception("WMI crash"), create=True)
def test_universal_thermal_wmi_fallback(mock_wmi):
    sampler = UniversalThermalSampler()
    snap = sampler.get_thermal_snapshot()
    assert snap.board_vendor is None


# ===========================================================================
# 5. Disk Tests (6)
# ===========================================================================

@patch("psutil.disk_usage")
def test_universal_disk_space_normal(mock_usage):
    mock_usage.return_value = MagicMock(total=1000, used=500, free=500, percent=50.0)
    sampler = UniversalDiskSampler()
    snap = sampler.get_space_snapshot()
    
    assert snap.total_bytes == 1000
    assert snap.used_bytes == 500
    assert snap.percent == 50.0

@patch("psutil.disk_usage", side_effect=PermissionError("Access Denied"))
def test_universal_disk_space_error(mock_usage):
    sampler = UniversalDiskSampler()
    snap = sampler.get_space_snapshot()
    
    assert snap.total_bytes is None
    assert snap.used_bytes is None

@patch("psutil.disk_io_counters")
def test_universal_disk_io_first_tick(mock_io):
    mock_io.return_value = {"sda": MagicMock(read_bytes=1000, write_bytes=1000)}
    sampler = UniversalDiskSampler()
    assert sampler.get_io_snapshot() == []

@patch("engine.universal_impl.universal_disk.time.monotonic")
@patch("psutil.disk_io_counters")
def test_universal_disk_io_delta_math(mock_io, mock_time):
    sampler = UniversalDiskSampler()
    
    mock_time.return_value = 100.0
    mock_io.return_value = {"sda": MagicMock(read_bytes=1000, write_bytes=1000)}
    sampler.get_io_snapshot() 
    
    mock_time.return_value = 101.0
    mock_io.return_value = {"sda": MagicMock(read_bytes=2000, write_bytes=1000)}
    snaps = sampler.get_io_snapshot()
    
    assert len(snaps) == 1
    assert snaps[0].read_bps == 1000.0
    assert snaps[0].write_bps == 0.0

@patch("engine.universal_impl.universal_disk.time.monotonic")
@patch("psutil.disk_io_counters")
def test_universal_disk_io_counter_reset(mock_io, mock_time):
    sampler = UniversalDiskSampler()
    
    mock_time.return_value = 100.0
    mock_io.return_value = {"sda": MagicMock(read_bytes=1000, write_bytes=1000)}
    sampler.get_io_snapshot()
    
    mock_time.return_value = 101.0
    mock_io.return_value = {"sda": MagicMock(read_bytes=500, write_bytes=1000)}
    snaps = sampler.get_io_snapshot()
    
    assert len(snaps) == 1
    assert snaps[0].read_bps == 0.0

@patch("engine.universal_impl.universal_disk.time.monotonic")
@patch("psutil.disk_io_counters")
def test_universal_disk_io_new_drive(mock_io, mock_time):
    sampler = UniversalDiskSampler()
    
    mock_time.return_value = 100.0
    mock_io.return_value = {"sda": MagicMock(read_bytes=1000, write_bytes=1000)}
    sampler.get_io_snapshot()
    
    mock_time.return_value = 101.0
    mock_io.return_value = {
        "sda": MagicMock(read_bytes=2000, write_bytes=1000),
        "sdb": MagicMock(read_bytes=5000, write_bytes=5000)
    }
    snaps = sampler.get_io_snapshot()
    
    assert len(snaps) == 1
    assert snaps[0].device == "sda"


# ===========================================================================
# 6. Network Tests (5)
# ===========================================================================

@patch("psutil.net_io_counters")
@patch("psutil.net_if_stats")
def test_universal_network_first_tick(mock_stats, mock_io):
    mock_stats.return_value = {"eth0": MagicMock(isup=True)}
    mock_io.return_value = {"eth0": MagicMock(bytes_recv=1000, bytes_sent=1000)}
    sampler = UniversalNetworkSampler()
    
    assert sampler.get_network_snapshot() == []

@patch("engine.universal_impl.universal_network.time.monotonic")
@patch("psutil.net_io_counters")
@patch("psutil.net_if_stats")
def test_universal_network_delta_math(mock_stats, mock_io, mock_time):
    sampler = UniversalNetworkSampler()
    mock_stats.return_value = {"eth0": MagicMock(isup=True)}
    
    mock_time.return_value = 100.0
    mock_io.return_value = {"eth0": MagicMock(bytes_recv=1000, bytes_sent=1000)}
    sampler.get_network_snapshot()
    
    mock_time.return_value = 101.0
    mock_io.return_value = {"eth0": MagicMock(bytes_recv=2000, bytes_sent=3000)}
    snaps = sampler.get_network_snapshot()
    
    assert len(snaps) == 1
    assert snaps[0].download_bps == 1000.0
    assert snaps[0].upload_bps == 2000.0

@patch("psutil.net_io_counters")
@patch("psutil.net_if_stats")
def test_universal_network_filters_loopback(mock_stats, mock_io):
    sampler = UniversalNetworkSampler()
    
    mock_stats.return_value = {
        "lo": MagicMock(isup=True),
        "WiFi": MagicMock(isup=True)
    }
    mock_io.return_value = {
        "lo": MagicMock(bytes_recv=100, bytes_sent=100),
        "WiFi": MagicMock(bytes_recv=100, bytes_sent=100)
    }
    
    sampler.get_network_snapshot() 
    snaps = sampler.get_network_snapshot()
    
    assert len(snaps) == 1 
    assert snaps[0].interface == "WiFi"

@patch("psutil.net_io_counters")
@patch("psutil.net_if_stats")
def test_universal_network_filters_virtual(mock_stats, mock_io):
    sampler = UniversalNetworkSampler()
    
    mock_stats.return_value = {
        "vEthernet (WSL)": MagicMock(isup=True),
        "eth0": MagicMock(isup=True)
    }
    mock_io.return_value = {
        "vEthernet (WSL)": MagicMock(bytes_recv=100, bytes_sent=100),
        "eth0": MagicMock(bytes_recv=100, bytes_sent=100)
    }
    
    sampler.get_network_snapshot() 
    snaps = sampler.get_network_snapshot()
    
    assert len(snaps) == 1
    assert snaps[0].interface == "eth0"

@patch("psutil.net_io_counters")
@patch("psutil.net_if_stats")
def test_universal_network_disconnected(mock_stats, mock_io):
    sampler = UniversalNetworkSampler()
    
    mock_stats.return_value = {"eth0": MagicMock(isup=True)}
    mock_io.return_value = {"eth0": MagicMock(bytes_recv=1000, bytes_sent=1000)}
    sampler.get_network_snapshot() 
    
    mock_stats.return_value = {"eth0": MagicMock(isup=False)}
    mock_io.return_value = {"eth0": MagicMock(bytes_recv=1000, bytes_sent=1000)}
    
    snaps = sampler.get_network_snapshot()
    
    assert len(snaps) == 1
    assert snaps[0].status == "DISCONNECTED"
    assert snaps[0].download_bps == 0.0
    assert snaps[0].upload_bps == 0.0