# Telemetry Engine

A high-performance, cross-platform system telemetry engine written in Python. It extracts deep system metrics by hooking directly into the Linux kernel virtual filesystem (`/proc` and `/sys`), while utilizing `subprocess` for low-level hardware queries. It provides a graceful `psutil` fallback for Windows, macOS, and restricted environments (like Docker containers).

---

## 🔥 Key Features

- **Cross-Platform Hardware Abstraction Layer (HAL):** Built on an Abstract Base Class (ABC) contract. The UI doesn't know or care if the data is coming from Linux kernel files, subprocesses, or Windows C-APIs; it just asks for the metrics.
- **Linux Kernel-Direct Hooking:** Reads natively from `/proc/stat`, `/proc/meminfo`, and `/sys/class/power_supply/` to capture bare-metal statistics with near-zero overhead.
- **Deep Thermal Diagnostics via Subprocess:** Parses `nvidia-smi` and `lm-sensors` JSON output to extract CPU/GPU temperatures and system fan speeds. Dynamically routes data based on hardware vendors (Intel, AMD, Lenovo, Dell, ASUS).
- **The Result Pattern (Fault Tolerance):** Hardware queries are wrapped in an `InternalResult` dataclass. If a driver crashes, a tool is missing, or JSON parsing fails, the engine returns a specific `ThermalError` enum instead of crashing the application.
- **Deep Battery Diagnostics:** Goes beyond basic percentages. Calculates real-time power draw (Watts), time remaining, and long-term hardware degradation (Health %).
- **Test-Driven Design:** Leverages dependency injection (`tmp_path`) and `unittest.mock.patch` for `subprocess`. The entire engine is completely testable on any machine without needing actual hardware.

---

## 🏗️ Project Layout

```text
telemetry-engine/
├── engine/
│   ├── __init__.py
│   ├── base_sampler.py    # Abstract Base Class (HAL contract)
│   ├── models.py          # Dataclasses for strict type enforcement
│   ├── linux_cpu.py       # Direct parsing mechanics for kernel scheduling
│   ├── linux_memory.py    # Memory structural parser
│   ├── linux_battery.py   # Direct ACPI/sysfs battery parsing
│   ├── linux_thermal.py   # Subprocess & JSON parsing for temps/fans
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
└── requirements.txt       # psutil, pytest
```

---

## 🚀 Getting Started

### Prerequisites

- **OS:** Linux (Ubuntu, Debian, Fedora, RHEL, or WSL2) OR Windows/macOS via `psutil`.
- **Python:** 3.10 or higher.
- **Optional (Linux Thermals):** `lm-sensors` package (`sudo apt install lm-sensors`) and proprietary NVIDIA drivers for `nvidia-smi`.

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
CPU Usage:                4.55%
------------------------------------
Total Memory:             7.42 GB
Used Memory:              2.45 GB
Available Memory:         4.96 GB
Memory Usage Percentage:  33.08%
====================================
         BATTERY TELEMETRY
====================================
Status:                   Discharging
Capacity:                 80%
Power Draw:               1.816 W
Time Estimate:            2h 11m remaining
Battery Health:           100.0%
====================================
         THERMAL TELEMETRY
====================================
CPU Vendor:               AMD
Motherboard:              Dell
CPU Temp:                 58.5°C (Max: 75.0°C)
Fan1:                     3100 RPM
GPU Status:               N/A (Driver not found)
====================================

Press Ctrl+C to exit.
```

---

## 🧪 Testing Suite Matrix

The suite isolates production code behavior from standard storage interfaces by injecting dynamically generated temporary file systems (`tmp_path`) and mocking `subprocess.run`.

Run the test collection using the `pytest` binary runner:

```bash
pytest -v
```

### Coverage Blueprint (17 Passing Tests)

- **Mathematical Accuracy:** Verifies unit conversion paths (Kilobytes/Gigabytes, MicroWatts/Watts) and CPU time delta operations.
- **Syntactical Resiliency:** Protects structural loops against arbitrary whitespace spacing and invalid non-colon configuration rows.
- **Hardware Mocking:** Uses `patch` to simulate `nvidia-smi` and `sensors -j` outputs across multiple hardware profiles (Intel/ThinkPad, AMD/Dell, AMD/ASUS).
- **Robustness Checks:** Forces edge situations including completely blank tracking paths, zero core totals, desktop fallbacks (no battery), and missing system key arrays.
- **Fault Tolerance:** Verifies that `FileNotFoundError`, `CalledProcessError`, `TimeoutExpired`, and malformed JSON are safely caught and returned as specific `ThermalError` states.
