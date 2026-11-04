import json
import subprocess
from unittest.mock import patch, MagicMock

import pynvml

from engine.linux_thermal import (
    LinuxThermalSampler,
    _DriverNotLoaded,
    _LibraryNotFound,
)
from engine.models import GpuInfo
from engine.results_and_errors import Errors, InternalResult


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
    cpu_vendor="Intel",
    board_vendor="Unknown",
):
    return InternalResult(data={
        "cpu_temp": cpu_temp,
        "cpu_max": cpu_max,
        "system_fans": fans or {},
        "cpu_vendor": cpu_vendor,
        "board_vendor": board_vendor,
    })


# ----------------------------------------------------------------
# NVML init classification (new — verifies the __init__ refactor)
# ----------------------------------------------------------------

def test_nvml_init_success_state():
    with patch("pynvml.nvmlInit"), patch("pynvml.nvmlShutdown"):
        sampler = LinuxThermalSampler()

    assert sampler._nvml_init_error is None
    assert sampler.initialized is True


def test_nvml_init_library_not_found_state():
    with patch("pynvml.nvmlInit", side_effect=_LibraryNotFound):
        sampler = LinuxThermalSampler()

    assert sampler._nvml_init_error == Errors.NOT_PRESENT
    assert sampler.initialized is False


def test_nvml_init_driver_not_loaded_state():
    with patch("pynvml.nvmlInit", side_effect=_DriverNotLoaded):
        sampler = LinuxThermalSampler()

    assert sampler._nvml_init_error == Errors.BROKEN_DRIVER
    assert sampler.initialized is False


def test_nvml_init_generic_nvml_error_state():
    with patch("pynvml.nvmlInit", side_effect=pynvml.NVMLError("boom")):
        sampler = LinuxThermalSampler()

    assert sampler._nvml_init_error == Errors.PYNVML_ERROR
    assert sampler.initialized is False


def test_nvml_init_unknown_error_state():
    with patch("pynvml.nvmlInit", side_effect=RuntimeError("boom")):
        sampler = LinuxThermalSampler()

    assert sampler._nvml_init_error == Errors.UNKNOWN
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
        result = sampler._get_nvidia()

        assert result.error is None
        assert result.data is not None
        gpus = result.data["gpus"]
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
        result = sampler._get_nvidia()

        assert result.error is None
        gpus = result.data["gpus"]
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
    # Laptop EC owns the fan; pynvml raises NotSupported, code should
    # record fan_speed_pct=None and still keep the GPU record.
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
        result = sampler._get_nvidia()

        assert result.error is None
        gpus = result.data["gpus"]
        assert len(gpus) == 1
        assert gpus[0].fan_speed_pct is None
        assert gpus[0].temperature_c == 60
        assert gpus[0].utilization_pct == 20
        assert gpus[0].power_w == 30.0


def test_nvidia_all_metrics_not_supported():
    # Pathological case: every metric unavailable, GPU still recorded.
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
        result = sampler._get_nvidia()

        assert result.error is None
        gpu = result.data["gpus"][0]
        assert gpu.temperature_c is None
        assert gpu.utilization_pct is None
        assert gpu.power_w is None
        assert gpu.fan_speed_pct is None


# ----------------------------------------------------------------
# NVIDIA error classification (via _nvml_init_error early return)
# ----------------------------------------------------------------

def test_nvidia_no_gpus():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=0):

        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()

        assert result.error == Errors.NOT_PRESENT
        assert result.data is None


def test_nvidia_library_not_found():
    with patch("pynvml.nvmlInit", side_effect=_LibraryNotFound):
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()

        assert result.error == Errors.NOT_PRESENT
        assert result.data is None


def test_nvidia_driver_not_loaded():
    with patch("pynvml.nvmlInit", side_effect=_DriverNotLoaded):
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()

        assert result.error == Errors.BROKEN_DRIVER
        assert result.data is None


def test_nvidia_generic_nvml_error():
    # Pass an instance of the error, not the class itself
    with patch("pynvml.nvmlInit", side_effect=pynvml.NVMLError("Generic Error")):
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()

        assert result.error == Errors.PYNVML_ERROR
        assert result.data is None


def test_nvidia_unknown_error():
    with patch("pynvml.nvmlInit", side_effect=RuntimeError("boom")):
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()

        assert result.error == Errors.UNKNOWN
        assert result.data is None


def test_get_nvidia_does_not_call_nvml_init():
    """Regression: nvmlInit lives in __init__, not _get_nvidia()."""
    with patch("pynvml.nvmlInit") as mock_init, \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=0):

        sampler = LinuxThermalSampler()
        assert mock_init.call_count == 1  # exactly once, in __init__

        sampler._get_nvidia()
        sampler._get_nvidia()

        assert mock_init.call_count == 1  # _get_nvidia must not re-init


# ----------------------------------------------------------------
# Sensors (subprocess + lm-sensors)
# ----------------------------------------------------------------

def test_sensors_thinkpad():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout=mock_sensors_thinkpad)

        sampler = LinuxThermalSampler()
        internal_data = sampler._get_sensors()

        assert internal_data.data["cpu_vendor"] == "Intel"
        assert internal_data.data["cpu_temp"] == 65.0
        assert internal_data.data["cpu_max"] == 80.0
        assert internal_data.data["board_vendor"] == "Lenovo (ThinkPad)"
        assert len(internal_data.data["system_fans"]) == 2
        assert internal_data.error is None


def test_sensors_amd_dell():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout=mock_sensors_amd)

        sampler = LinuxThermalSampler()
        internal_data = sampler._get_sensors()

        assert internal_data.data["cpu_vendor"] == "AMD"
        assert internal_data.data["board_vendor"] == "Dell"
        assert internal_data.error is None


def test_sensors_asus():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout=mock_sensors_asus)

        sampler = LinuxThermalSampler()
        internal_data = sampler._get_sensors()

        assert internal_data.data["cpu_vendor"] == "AMD"
        assert internal_data.data["board_vendor"] == "ASUS"
        assert internal_data.error is None


def test_errors_sensors():
    # sensors binary missing -> SENSORS_NOT_INSTALLED
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = LinuxThermalSampler()._get_sensors()
        assert result.error == Errors.SENSORS_NOT_INSTALLED
        assert result.data is None

    # sensors not executable -> PERMISSION_DENIED
    with patch("subprocess.run", side_effect=PermissionError):
        result = LinuxThermalSampler()._get_sensors()
        assert result.error == Errors.PERMISSION_DENIED
        assert result.data is None

    # sensors exited non-zero -> SENSORS_ERROR
    with patch("subprocess.run",
               side_effect=subprocess.CalledProcessError(returncode=1, cmd="sensors")):
        result = LinuxThermalSampler()._get_sensors()
        assert result.error == Errors.SENSORS_ERROR
        assert result.data is None

    # sensors hung -> TIMEOUT
    with patch("subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="sensors", timeout=2)):
        result = LinuxThermalSampler()._get_sensors()
        assert result.error == Errors.TIMEOUT
        assert result.data is None

    # malformed JSON -> PARSE_FAILED
    with patch("subprocess.run",
               side_effect=json.decoder.JSONDecodeError(
                   msg="Expecting value", doc="{invalid json}", pos=1)):
        result = LinuxThermalSampler()._get_sensors()
        assert result.error == Errors.PARSE_FAILED
        assert result.data is None

    # anything else -> UNKNOWN
    with patch("subprocess.run", side_effect=TypeError):
        result = LinuxThermalSampler()._get_sensors()
        assert result.error == Errors.UNKNOWN
        assert result.data is None


# ----------------------------------------------------------------
# get_thermal_snapshot: integration + 3-second cache
# ----------------------------------------------------------------

def test_thermal_snapshot_full():
    gpu = GpuInfo(index=0, name="RTX 3080", temperature_c=45,
                  utilization_pct=67, power_w=150.0, fan_speed_pct=55)

    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch.object(LinuxThermalSampler, "_get_nvidia",
                      return_value=InternalResult(data={"gpus": [gpu]})), \
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
        assert snap.gpu_error is None
        assert snap.sensor_error is None


def test_thermal_snapshot_cache_hit():
    """Two calls inside the 3s window must hit the cache."""
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch.object(LinuxThermalSampler, "_get_nvidia",
                      return_value=InternalResult(data={"gpus": []})) as mock_nv, \
         patch.object(LinuxThermalSampler, "_get_sensors",
                      return_value=_sensor_data()) as mock_sensors:

        sampler = LinuxThermalSampler()
        snap1 = sampler.get_thermal_snapshot()
        snap2 = sampler.get_thermal_snapshot()

        assert snap1 is snap2
        assert mock_nv.call_count == 1
        assert mock_sensors.call_count == 1


def test_thermal_snapshot_cache_expiry():
    """A call past the 3s window must re-sample."""
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch.object(LinuxThermalSampler, "_get_nvidia",
                      return_value=InternalResult(data={"gpus": []})) as mock_nv, \
         patch.object(LinuxThermalSampler, "_get_sensors",
                      return_value=_sensor_data()) as mock_sensors:

        sampler = LinuxThermalSampler()
        snap1 = sampler.get_thermal_snapshot()

        # Fast-forward the cache timestamp by >3s
        sampler._last_thermal_time -= 4.0

        snap2 = sampler.get_thermal_snapshot()

        assert snap1 is not snap2
        assert mock_nv.call_count == 2
        assert mock_sensors.call_count == 2