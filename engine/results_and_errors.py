from enum import Enum
from dataclasses import dataclass
from typing import Any

class Errors(Enum):
    # pynvml / NVML
    NOT_PRESENT        = "No NVIDIA GPU detected or driver/NVML not installed."
    BROKEN_DRIVER      = "NVIDIA driver is installed but not loaded / crashed."
    PYNVML_ERROR       = "Generic NVML error occurred."
    # sensors CLI
    NOT_FOUND          = "Required tool (e.g. nvidia-smi) not found."   # reserved
    SENSORS_NOT_INSTALLED = "`sensors` command not installed or not executable."
    SENSORS_ERROR      = "`sensors` command returned a non-zero exit code."
    # generic
    TIMEOUT            = "Hardware query timed out."
    PARSE_FAILED       = "Could not parse hardware output (format changed)."
    UNKNOWN            = "An unknown error occurred."
    # filesystem (used when reading files, e.g. /sys or configs)
    FILE_NOT_FOUND     = "Failed to locate the required file or folder."
    PERMISSION_DENIED  = "Permission denied while accessing hardware."
    
    
@dataclass(frozen=True)
class InternalResult:
    data: list[dict[str, Any]] |dict[str, Any] | None = None
    error: Errors | None = None
