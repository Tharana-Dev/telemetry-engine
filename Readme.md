# Telemetry Engine

A high-performance, cross-platform system telemetry engine written in Python. It extracts deep system metrics by hooking directly into the Linux kernel virtual filesystem (`/proc` and `/sys`), while providing a graceful `psutil` fallback for Windows, macOS, and restricted environments (like Docker containers).

---

## 🔥 Key Features

- **Cross-Platform Hardware Abstraction Layer (HAL):** Built on an Abstract Base Class (ABC) contract. The UI doesn't know or care if the data is coming from Linux kernel files or Windows C-APIs; it just asks for the metrics.
- **Linux Kernel-Direct Hooking:** Reads natively from `/proc/stat`, `/proc/meminfo`, and `/sys/class/power_supply/` to capture bare-metal statistics with near-zero overhead.
- **Graceful Degradation:** Automatically detects if the Linux virtual filesystem is locked or missing (e.g., in a Docker sandbox) and seamlessly falls back to `psutil` without crashing.
- **Deep Battery Diagnostics:** Goes beyond basic percentages. Calculates real-time power draw (Watts), time remaining, and long-term hardware degradation (Health %).
- **Defensive Error Handling:** Empty file outputs, missing kernel keys, or system data anomalies safely return null-state fallback snapshots instead of raising fatal errors.
- **Test-Driven Design:** Leverages dependency injection (`stat_path`, `mem_path`, `sys_path`), making the entire engine completely testable without mocking core Python I/O modules.

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
│   ├── linux_sampler.py   # Linux adapter bridging the HAL to raw parsers
│   └── psutil_sampler.py  # Universal cross-platform fallback driver
├── tests/
│   ├── fixtures/
│   ├── test_cpu.py        
│   ├── test_memory.py
│   ├── test_battery.py
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
CPU Usage:                0.43%
------------------------------------
Total Memory:             7.42 GB
Used Memory:              2.85 GB
Available Memory:         4.57 GB
Memory Usage Percentage:  38.36%
====================================
         BATTERY TELEMETRY
====================================
Status:                   Discharging
Capacity:                 79%
Power Draw:               1.816 W
Time Estimate:            2h 11m remaining
Battery Health:           100.0%
====================================

Press Ctrl+C to exit.
```

---

## 🧪 Testing Suite Matrix

The suite isolates production code behavior from standard storage interfaces by injecting dynamically generated temporary file systems (`tmp_path`).

Run the test collection using the `pytest` binary runner:

```bash
pytest -v
```

### Coverage Blueprint (12 Passing Tests)

- **Mathematical Accuracy:** Verifies unit conversion paths (Kilobytes/Gigabytes, MicroWatts/Watts) and CPU time delta operations.
- **Syntactical Resiliency:** Protects structural loops against arbitrary whitespace spacing and invalid non-colon configuration rows.
- **Robustness Checks:** Forces edge situations including completely blank tracking paths, zero core totals, desktop fallbacks (no battery), and missing system key arrays.
- **Mocking:** Verifies that `psutil` correctly maps to the engine's dataclasses when running on Windows/macOS.
