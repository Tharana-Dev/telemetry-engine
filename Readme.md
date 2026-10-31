# Telemetry Engine

A high-performance, cross-platform system telemetry engine written in Python. It extracts deep system metrics by hooking directly into the Linux kernel virtual filesystem (`/proc` and `/sys`), utilizing `pynvml` for direct GPU driver access, and providing a graceful `psutil` fallback for Windows, macOS, and restricted environments.

---

## 🔥 Key Features

- **Cross-Platform Hardware Abstraction Layer (HAL):** Built on an Abstract Base Class (ABC) contract. The UI doesn't know or care if the data is coming from Linux kernel files, C-bindings, or Windows C-APIs; it just asks for the metrics.
- **Linux Kernel-Direct Hooking:** Reads natively from `/proc/stat`, `/proc/meminfo`, and `/sys/class/power_supply/` to capture bare-metal statistics with near-zero overhead.
- **Direct GPU Telemetry via NVML:** Drops fragile CLI parsing (`nvidia-smi`) in favor of NVIDIA's official C-bindings (`pynvml`). Supports multi-GPU setups, queries temperature, utilization, and power draw directly from the driver, and handles laptop Embedded Controller (EC) fan restrictions.
- **Deep Thermal Diagnostics:** Parses `lm-sensors` JSON output to extract CPU and Motherboard temperatures, dynamically mapping vendors (Intel, AMD, Lenovo, Dell, ASUS).
- **The Result Pattern (Fault Tolerance):** Hardware queries are wrapped in an `InternalResult` dataclass. If a driver crashes, a tool is missing, or JSON parsing fails, the engine returns a specific `ThermalError` enum instead of crashing.
- **Deep Battery Diagnostics:** Goes beyond basic percentages. Calculates real-time power draw (Watts), time remaining, and long-term hardware degradation (Health %), with fallbacks for both `energy_*` and `charge_*` sysfs paths.

---

## 🏗️ Project Layout

```text
telemetry-engine/
├── engine/
│   ├── __init__.py
│   ├── base_sampler.py    # Abstract Base Class (HAL contract)
│   ├── models.py          # Dataclasses for strict type enforcement
│   ├── linux_cpu.py       # Direct parsing for kernel scheduling
│   ├── linux_memory.py    # Memory structural parser
│   ├── linux_battery.py   # ACPI/sysfs battery parsing
│   ├── linux_thermal.py   # NVML & lm-sensors JSON parsing
│   ├── linux_sampler.py   # Linux adapter bridging the HAL to raw parsers
│   └── psutil_sampler.py  # Universal cross-platform fallback driver
├── tests/
│   ├── fixtures/
│   ├── test_cpu.py        
│   ├── test_memory.py
│   ├── test_battery.py
│   ├── test_linux_thermals.py
│   └── test_psutil.py
├── main.py                # Main executable application orchestrator
├── README.md              
└── requirements.txt       # psutil, pynvml, pytest
```

---

## 🚀 Getting Started

### Prerequisites

- **OS:** Linux (Ubuntu, Debian, Fedora, RHEL, or WSL2) OR Windows/macOS via `psutil`.
- **Python:** 3.10 or higher.
- **Optional (Linux Thermals):** `lm-sensors` package (`sudo apt install lm-sensors`) and proprietary NVIDIA drivers.

### 1. Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🖥️ Running the Application

Launch the live telemetry dashboard stream directly from the console interface:

```bash
python3 main.py
```

### Expected Output Terminal UI

```text
====================================
      SYSTEM TELEMETRY ENGINE
====================================
[*] ENGINE MODE: High-Performance Linux Native (/proc)
------------------------------------
CPU Usage:                4.03%
------------------------------------
Total Memory:             7.42 GB
Used Memory:              2.62 GB
Available Memory:         4.79 GB
Memory Usage Percentage:  35.37%
====================================
         BATTERY TELEMETRY
====================================
Status:                   Not charging
Capacity:                 80%
Power Draw:               N/A (OS Wrapper Restriction)
Time Estimate:            Wall Power (AC)
Battery Health:           100.0%
====================================
         THERMAL TELEMETRY
====================================
CPU Vendor:               Unknown
Motherboard:              Unknown
CPU Temp:                 N/A (Max: N/A)
System Fans:              N/A
GPU [0]:                  NVIDIA GeForce RTX 4050 Laptop GPU
  Temp / Util:            49°C / 0%
  Power Draw:             14.26 W
  Fan Speed:              N/A (EC Owned)
====================================

Press Ctrl+C to exit.
```

---

## 🧪 Testing Suite Matrix

The suite isolates production code behavior from standard storage interfaces by injecting dynamically generated temporary file systems (`tmp_path`), mocking `subprocess.run` for sensors, and mocking `pynvml` for GPU telemetry.

Run the test collection using the `pytest` binary runner:

```bash
pytest -v
```

### Coverage Blueprint (20+ Passing Tests)

- **Mathematical Accuracy:** Verifies unit conversion paths (Kilobytes/Gigabytes, MicroWatts/Watts) and CPU time delta operations.
- **Hardware Mocking (GPU):** Verifies that `pynvml` successfully extracts temperature, utilization, and power draw, while gracefully catching `NVMLError_NotSupported` for fan speeds.
- **Hardware Mocking (Sensors):** Uses `patch` to simulate `lm-sensors` outputs across multiple hardware profiles (Intel/ThinkPad, AMD/Dell, AMD/ASUS).
- **Robustness Checks:** Forces edge situations including completely blank tracking paths, zero core totals, desktop fallbacks, and missing system key arrays.
- **Fault Tolerance:** Verifies that `FileNotFoundError`, `CalledProcessError`, `TimeoutExpired`, and malformed JSON are safely caught and returned as specific error states.
