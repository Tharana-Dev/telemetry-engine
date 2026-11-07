import subprocess
from unittest.mock import patch, MagicMock

import pytest
import pynvml

from engine.linux_thermal import LinuxThermalSampler
from engine.models import GpuInfo


# ----------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------

mock_sensors_thinkpad = """
{
   "coretemp-isa-0000": {
      "Adapter": "ISA adapter",
      "Package id 0": {
         "temp1_input": 65.0,
         "temp1_max": 80.0
      }
   },
   "thinkpad-isa-0000": {
      "Adapter": "ISA adapter",
      "fan1": { "fan1_input": 2400.0 },
      "fan2": { "fan2_input": 1800.0 }
   }
}
"""

mock_sensors_amd = """
{
   "k10temp-pci-00c3": {
      "Adapter": "PCI adapter",
      "Package id 0": {
         "temp1_input": 58.5,
         "temp1_max": 75.0
      }
   },
   "dell_smm-isa-0000": {
      "Adapter": "ISA adapter",
      "fan1": { "fan1_input": 3100.0 },
      "fan2": { "fan2_input": 2900.0 }
   }
}
"""

mock_sensors_asus = """
{
   "zenpower-pci-00c3": {
      "Adapter": "PCI adapter",
      "Package id 0": {
         "temp1_input": 61.0,
         "temp1_max": 85.0
      }
   },
   "asus-isa-0000": {
      "Adapter": "ISA adapter",
      "fan1": { "fan1_input": 4000.0 }
   }
}
"""


class FakeCompletedProcess:
    def __init__(self, stdout) -> None:
        self.stdout = stdout


def _sensor_data(
    cpu_temp=50.0,
    cpu_max=80.0,
    fans=None,
    cpu_vendor=None,
    board_vendor=None,
):
    """Return the dict shape that _get_sensors() produces."""
    return {
        "cpu_temp": cpu_temp,
        "cpu_max": cpu_max,
        "system_fans": fans or {},
        "cpu_vendor": cpu_vendor,
        "board_vendor": board_vendor,
    }


# ----------------------------------------------------------------
# NVML init (refactored: all failure modes collapse to initialized=False)
# ----------------------------------------------------------------

def test_nvml_init_success_state():
    with patch("pynvml.nvmlInit"), patch("pynvml.nvmlShutdown"):
        sampler = LinuxThermalSampler()

    assert sampler.initialized is True


@pytest.mark.parametrize("exc", [
    # NVMLError must be constructed with a *numeric* error code —
    # its __str__ falls back to "%d format" on .value when nvmlErrorString
    # is unavailable, so a string code raises TypeError on logging.
    pynvml.NVMLError(pynvml.NVML_ERROR_UNINITIALIZED),
    RuntimeError("boom"),
    Exception("boom"),
])
def test_nvml_init_failure_leaves_uninitialized(exc):
    """All init failures collapse to initialized=False."""
    with patch("pynvml.nvmlInit", side_effect=exc):
        sampler = LinuxThermalSampler()

    assert sampler.initialized is False


# ----------------------------------------------------------------
# NVIDIA happy-path / multi-GPU
# ----------------------------------------------------------------

def test_nvidia_happy_path():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=1), \
         patch("pynvml.nvmlDeviceGetHandleByIndex", return_value="handle0"), \
         patch("pynvml.nvmlDeviceGetName", return_value=b"NVIDIA GeForce RTX 3080"), \
         patch("pynvml.nvmlDeviceGetTemperature", return_value=45), \
         patch("pynvml.nvmlDeviceGetUtilizationRates",
               return_value=MagicMock(gpu=67)), \
         patch("pynvml.nvmlDeviceGetPowerUsage", return_value=150000), \
         patch("pynvml.nvmlDeviceGetFanSpeed", return_value=55):

        sampler = LinuxThermalSampler()
        gpus = sampler._get_nvidia()

        assert len(gpus) == 1
        gpu = gpus[0]
        assert gpu.index == 0
        assert gpu.name == "NVIDIA GeForce RTX 3080"
        assert gpu.temperature_c == 45
        assert gpu.utilization_pct == 67
        assert gpu.power_w == 150.0
        assert gpu.fan_speed_pct == 55


def test_nvidia_multiple_gpus():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=2), \
         patch("pynvml.nvmlDeviceGetHandleByIndex", side_effect=["h0", "h1"]), \
         patch("pynvml.nvmlDeviceGetName", side_effect=["GPU-A", "GPU-B"]), \
         patch("pynvml.nvmlDeviceGetTemperature", side_effect=[50, 60]), \
         patch("pynvml.nvmlDeviceGetUtilizationRates",
               return_value=MagicMock(gpu=30)), \
         patch("pynvml.nvmlDeviceGetPowerUsage", return_value=100000), \
         patch("pynvml.nvmlDeviceGetFanSpeed", return_value=40):

        sampler = LinuxThermalSampler()
        gpus = sampler._get_nvidia()

        assert len(gpus) == 2
        assert gpus[0].name == "GPU-A"
        assert gpus[0].temperature_c == 50
        assert gpus[0].power_w == 100.0
        assert gpus[1].name == "GPU-B"
        assert gpus[1].temperature_c == 60


# ----------------------------------------------------------------
# NVIDIA per-metric NotSupported handling
# ----------------------------------------------------------------

def test_nvidia_fan_not_supported():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=1), \
         patch("pynvml.nvmlDeviceGetHandleByIndex", return_value="handle0"), \
         patch("pynvml.nvmlDeviceGetName", return_value="Laptop GPU"), \
         patch("pynvml.nvmlDeviceGetTemperature", return_value=60), \
         patch("pynvml.nvmlDeviceGetUtilizationRates",
               return_value=MagicMock(gpu=20)), \
         patch("pynvml.nvmlDeviceGetPowerUsage", return_value=30000), \
         patch("pynvml.nvmlDeviceGetFanSpeed",
               side_effect=pynvml.NVMLError_NotSupported):

        sampler = LinuxThermalSampler()
        gpus = sampler._get_nvidia()

        assert len(gpus) == 1
        assert gpus[0].fan_speed_pct is None
        assert gpus[0].temperature_c == 60
        assert gpus[0].utilization_pct == 20
        assert gpus[0].power_w == 30.0


def test_nvidia_all_metrics_not_supported():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=1), \
         patch("pynvml.nvmlDeviceGetHandleByIndex", return_value="handle0"), \
         patch("pynvml.nvmlDeviceGetName", return_value="Ghost GPU"), \
         patch("pynvml.nvmlDeviceGetTemperature",
               side_effect=pynvml.NVMLError_NotSupported), \
         patch("pynvml.nvmlDeviceGetUtilizationRates",
               side_effect=pynvml.NVMLError_NotSupported), \
         patch("pynvml.nvmlDeviceGetPowerUsage",
               side_effect=pynvml.NVMLError_NotSupported), \
         patch("pynvml.nvmlDeviceGetFanSpeed",
               side_effect=pynvml.NVMLError_NotSupported):

        sampler = LinuxThermalSampler()
        gpus = sampler._get_nvidia()

        assert len(gpus) == 1
        gpu = gpus[0]
        assert gpu.temperature_c is None
        assert gpu.utilization_pct is None
        assert gpu.power_w is None
        assert gpu.fan_speed_pct is None


# ----------------------------------------------------------------
# NVIDIA "no hardware / no driver" -> empty list
# ----------------------------------------------------------------

def test_nvidia_no_gpus():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=0):

        sampler = LinuxThermalSampler()
        assert sampler._get_nvidia() == []


@pytest.mark.parametrize("exc", [
    # Must be a numeric NVML code; a string value makes str(exc) raise
    # TypeError via "%d format" when the sampler logs the failure.
    pynvml.NVMLError(pynvml.NVML_ERROR_UNINITIALIZED),
    RuntimeError("boom"),
])
def test_nvidia_returns_empty_when_nvml_init_failed(exc):
    """Init failed -> _get_nvidia() short-circuits to [] without touching NVML."""
    with patch("pynvml.nvmlInit", side_effect=exc):
        sampler = LinuxThermalSampler()
        assert sampler._get_nvidia() == []


def test_get_nvidia_does_not_call_nvml_init():
    """Regression: nvmlInit lives in __init__, not _get_nvidia()."""
    with patch("pynvml.nvmlInit") as mock_init, \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=0):

        sampler = LinuxThermalSampler()
        assert mock_init.call_count == 1

        sampler._get_nvidia()
        sampler._get_nvidia()

        assert mock_init.call_count == 1


# ----------------------------------------------------------------
# Sensors (subprocess + lm-sensors)
# ----------------------------------------------------------------

def test_sensors_thinkpad():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout=mock_sensors_thinkpad)

        sampler = LinuxThermalSampler()
        data = sampler._get_sensors()

        assert data is not None
        assert data["cpu_vendor"] == "Intel"
        assert data["cpu_temp"] == 65.0
        assert data["cpu_max"] == 80.0
        assert data["board_vendor"] == "Lenovo (ThinkPad)"
        assert len(data["system_fans"]) == 2


def test_sensors_amd_dell():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout=mock_sensors_amd)

        sampler = LinuxThermalSampler()
        data = sampler._get_sensors()

        assert data is not None
        assert data["cpu_vendor"] == "AMD"
        assert data["board_vendor"] == "Dell"


def test_sensors_asus():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout=mock_sensors_asus)

        sampler = LinuxThermalSampler()
        data = sampler._get_sensors()

        assert data is not None
        assert data["cpu_vendor"] == "AMD"
        assert data["board_vendor"] == "ASUS"


def test_errors_sensors():
    """Every failure mode returns None (sensor_available=False downstream)."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert LinuxThermalSampler()._get_sensors() is None

    with patch("subprocess.run", side_effect=PermissionError):
        assert LinuxThermalSampler()._get_sensors() is None

    with patch("subprocess.run",
               side_effect=subprocess.CalledProcessError(returncode=1, cmd="sensors")):
        assert LinuxThermalSampler()._get_sensors() is None

    with patch("subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="sensors", timeout=2)):
        assert LinuxThermalSampler()._get_sensors() is None

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout="{invalid json}")
        assert LinuxThermalSampler()._get_sensors() is None

    with patch("subprocess.run", side_effect=TypeError):
        assert LinuxThermalSampler()._get_sensors() is None


# ----------------------------------------------------------------
# get_thermal_snapshot: integration + 3-second cache
# ----------------------------------------------------------------

def test_thermal_snapshot_full():
    gpu = GpuInfo(index=0, name="RTX 3080", temperature_c=45,
                  utilization_pct=67, power_w=150.0, fan_speed_pct=55)

    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch.object(LinuxThermalSampler, "_get_nvidia",
                      return_value=[gpu]), \
         patch.object(LinuxThermalSampler, "_get_sensors",
                      return_value=_sensor_data(
                          cpu_temp=65.0, cpu_max=80.0,
                          fans={"fan1": 2400.0},
                          cpu_vendor="Intel",
                          board_vendor="Lenovo (ThinkPad)")):

        snap = LinuxThermalSampler().get_thermal_snapshot()

        assert snap.cpu_temp == 65.0
        assert snap.cpu_temp_max == 80.0
        assert snap.system_fans == {"fan1": 2400}
        assert len(snap.gpus) == 1
        assert snap.gpus[0].name == "RTX 3080"
        assert snap.gpu_available is True
        assert snap.sensor_available is True
        assert snap.cpu_vendor == "Intel"
        assert snap.board_vendor == "Lenovo (ThinkPad)"


def test_thermal_snapshot_no_gpu_no_sensors():
    with patch("pynvml.nvmlInit", side_effect=RuntimeError), \
         patch.object(LinuxThermalSampler, "_get_nvidia", return_value=[]), \
         patch.object(LinuxThermalSampler, "_get_sensors", return_value=None):

        snap = LinuxThermalSampler().get_thermal_snapshot()

        assert snap.gpu_available is False
        assert snap.sensor_available is False
        assert snap.gpus == []
        assert snap.cpu_temp is None
        assert snap.cpu_temp_max is None
        assert snap.system_fans is None
        assert snap.cpu_vendor is None
        assert snap.board_vendor is None


def test_thermal_snapshot_cache_hit():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch.object(LinuxThermalSampler, "_get_nvidia",
                      return_value=[]) as mock_nv, \
         patch.object(LinuxThermalSampler, "_get_sensors",
                      return_value=_sensor_data()) as mock_sensors:

        sampler = LinuxThermalSampler()
        snap1 = sampler.get_thermal_snapshot()
        snap2 = sampler.get_thermal_snapshot()

        assert snap1 is snap2
        assert mock_nv.call_count == 1
        assert mock_sensors.call_count == 1


def test_thermal_snapshot_cache_expiry():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch.object(LinuxThermalSampler, "_get_nvidia",
                      return_value=[]) as mock_nv, \
         patch.object(LinuxThermalSampler, "_get_sensors",
                      return_value=_sensor_data()) as mock_sensors:

        sampler = LinuxThermalSampler()
        snap1 = sampler.get_thermal_snapshot()

        sampler._last_thermal_time -= 4.0

        snap2 = sampler.get_thermal_snapshot()

        assert snap1 is not snap2
        assert mock_nv.call_count == 2
        assert mock_sensors.call_count == 2