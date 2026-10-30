from unittest.mock import patch
import subprocess
from engine.linux_thermal import LinuxThermalSampler, ThermalError
import json


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

# 2. CORRECTED: True AMD + Dell configuration
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

# 3. ANOTHER OPTION: AMD + ASUS configuration
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

mock_nvidia = """
{
    "gpu": [
        {
            "temperature": {
                "gpu": 45
            },
            "fan": {
                "speed": "[N/A]"
            }
        }
    ]
}
"""

class FakeCompletedProcess:
    def __init__(self,stdout) -> None:
        self.stdout = stdout
        
def test_nvidia_happy_path():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = FakeCompletedProcess(stdout=mock_nvidia)
        
        sampler = LinuxThermalSampler()
        internal_result = sampler._get_nvidia()
        
        assert internal_result.data["temp"] == 45
        assert internal_result.data["fan"] is None
        assert internal_result.error is None

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

def test_errors_sensors():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError
        
        sampler = LinuxThermalSampler()
        result = sampler._get_sensors()
        
        assert result.error == ThermalError.NOT_FOUND
        assert result.data is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="nvidia-smi")
        
        sampler = LinuxThermalSampler()
        result = sampler._get_sensors()
        
        assert result.error == ThermalError.BROKEN_DRIVER
        assert result.data is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2)
        
        sampler = LinuxThermalSampler()
        result = sampler._get_sensors()
        
        assert result.error == ThermalError.TIMEOUT
        assert result.data is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = json.decoder.JSONDecodeError(
            msg="Expecting value", 
            doc="{invalid json}", 
            pos=1
        )
        
        sampler = LinuxThermalSampler()
        result = sampler._get_sensors()
        
        assert result.error == ThermalError.PARSE_FAILED
        assert result.data is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = TypeError
        
        sampler = LinuxThermalSampler()
        result = sampler._get_sensors()
        
        assert result.error == ThermalError.UNKNOWN
        assert result.data is None

def test_errors_nvidia():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError
        
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()
        
        assert result.error == ThermalError.NOT_FOUND
        assert result.data is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="nvidia-smi")
        
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()
        
        assert result.error == ThermalError.BROKEN_DRIVER
        assert result.data is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2)
        
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()
        
        assert result.error == ThermalError.TIMEOUT
        assert result.data is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = json.decoder.JSONDecodeError(
            msg="Expecting value", 
            doc="{invalid json}", 
            pos=1
        )
        
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()
        
        assert result.error == ThermalError.PARSE_FAILED
        assert result.data is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = OSError
        
        sampler = LinuxThermalSampler()
        result = sampler._get_nvidia()
        
        assert result.error == ThermalError.UNKNOWN
        assert result.data is None