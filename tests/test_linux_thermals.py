from unittest.mock import patch, MagicMock
import subprocess
from engine.linux_thermal import LinuxThermalSampler
from engine.results_and_errors import Errors
import json
import pynvml


# Pylance's pynvml stubs don't know about NVMLError_LibraryNotFound, but the
# runtime module does define it. getattr() returns Any, so the type checker
# stops complaining, and the fallback to NVMLError keeps the test valid even
# if a future pynvml version removes the name.
_LibraryNotFound = getattr(pynvml, "NVMLError_LibraryNotFound", pynvml.NVMLError)


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


# ----------------------------------------------------------------
# NVIDIA (pynvml) tests
# ----------------------------------------------------------------

def test_nvidia_happy_path():
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=1), \
         patch("pynvml.nvmlDeviceGetHandleByIndex", return_value="handle0"), \
         patch("pynvml.nvmlDeviceGetName", return_value=b"NVIDIA GeForce RTX 3080"), \
         patch("pynvml.nvmlDeviceGetTemperature", return_value=45), \
         patch("pynvml.nvmlDeviceGetUtilizationRates", return_value=MagicMock(gpu=67)), \
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
         patch("pynvml.nvmlDeviceGetUtilizationRates", return_value=MagicMock(gpu=30)), \
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


def test_nvidia_fan_not_supported():
    # Laptop EC owns the fan; pynvml raises NotSupported, code should
    # record fan_speed_pct=None and still keep the GPU record.
    with patch("pynvml.nvmlInit"), \
         patch("pynvml.nvmlShutdown"), \
         patch("pynvml.nvmlDeviceGetCount", return_value=1), \
         patch("pynvml.nvmlDeviceGetHandleByIndex", return_value="handle0"), \
         patch("pynvml.nvmlDeviceGetName", return_value="Laptop GPU"), \
         patch("pynvml.nvmlDeviceGetTemperature", return_value=60), \
         patch("pynvml.nvmlDeviceGetUtilizationRates", return_value=MagicMock(gpu=20)), \
         patch("pynvml.nvmlDeviceGetPowerUsage", return_value=30000), \
         patch("pynvml.nvmlDeviceGetFanSpeed",
               side_effect=pynvml.NVMLError_NotSupported):

        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()

        assert result.error is None
        gpus = result.data["gpus"]
        assert len(gpus) == 1
        assert gpus[0].fan_speed_pct is None
        # Other metrics still populated
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


# ----------------------------------------------------------------
# Sensors (subprocess + lm-sensors) tests
# ----------------------------------------------------------------

def test_sensors_thinkpad():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout=mock_sensors_thinkpad)

        sampler = LinuxThermalSampler()
        internal_data = sampler._get_sensors()

        assert internal_data.data["cpu_vendor"] == "Intel"
        assert internal_data.data["cpu_temp"] == 65.0
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