# Telemetry Engine

A high-performance, cross-platform system telemetry engine written in Python. It extracts deep system metrics by hooking directly into the Linux kernel virtual filesystem (`/proc` and `/sys`), utilizing `nvidia-ml-py` for direct GPU driver access, and providing a graceful `psutil` fallback for Windows, macOS, and restricted environments.

---

## 🔥 Key Features

- **Cross-Platform Hardware Abstraction Layer (HAL):** Built on an Abstract Base Class (ABC) contract. The UI doesn't know or care if the data is coming from Linux kernel files, C-bindings, or Windows C-APIs; it just asks for the metrics.
- **Linux Kernel-Direct Hooking:** Reads natively from `/proc/stat`, `/proc/meminfo`, `/proc/diskstats`, `/proc/net/dev`, and `/sys/class/power_supply/` to capture bare-metal statistics.
- **Network Telemetry:** Calculates real-time upload and download speeds (Mbps) by tracking byte deltas in `/proc/net/dev`. Safely handles interface hot-plugging, disconnections, and kernel counter resets. Filters out virtual interfaces (like `lo` and `docker0`).
- **Disk I/O & Capacity:** Calculates real-time read/write speeds (MB/s) by tracking sector deltas in `/proc/diskstats`, filtering out virtual drives (`loop0`) and partitions. Uses `psutil` for accurate root partition capacity.
- **Direct GPU Telemetry via NVML:** Drops fragile CLI parsing in favor of NVIDIA's official C-bindings. Supports multi-GPU setups, queries temperature, utilization, and power draw, and handles laptop EC fan restrictions.
- **The Result Pattern (Fault Tolerance):** Hardware queries are wrapped in an `InternalResult` dataclass. If a driver crashes or a tool is missing, the engine returns a specific error enum instead of crashing.
- **Resilient Battery Diagnostics:** Calculates real-time power draw (Watts), time remaining, and hardware degradation (Health %), with fallbacks for both `energy_*` and `charge_*` sysfs paths.

---

## 🏗️ Project Layout

```text
telemetry-engine/
├── engine/
│   ├── __init__.py
│   ├── base_sampler.py    # Abstract Base Class (HAL contract)
│   ├── models.py          # Dataclasses for strict type enforcement
│   ├── results_and_errors.py # Enums for fault tolerance
│   ├── linux_cpu.py       # Direct parsing for kernel scheduling
│   ├── linux_memory.py    # Memory structural parser
│   ├── linux_battery.py   # ACPI/sysfs battery parsing
│   ├── linux_thermal.py   # NVML & lm-sensors JSON parsing
│   ├── linux_disk.py      # /proc/diskstats parsing & space telemetry
│   ├── linux_network.py   # /proc/net/dev parsing
│   ├── linux_sampler.py   # Linux adapter bridging the HAL to raw parsers
│   └── psutil_sampler.py  # Universal cross-platform fallback driver
├── tests/
│   ├── fixtures/
│   ├── test_cpu.py        
│   ├── test_memory.py
│   ├── test_battery.py
│   ├── test_linux_thermals.py
│   ├── test_linux_disk.py
│   ├── test_linux_network.py
│   └── test_psutil.py
├── main.py                # Main executable orchestrator
├── README.md              
└── requirements.txt       
```

## 🚀 Getting Started

### Prerequisites

- **OS:** Linux (Ubuntu, Debian, Fedora, RHEL, or WSL2) OR Windows/macOS via `psutil`.
- **Python:** 3.10 or higher.
- **Optional (Linux Thermals):** `lm-sensors` package (`sudo apt install lm-sensors`) and proprietary NVIDIA drivers.

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/Tharana-Dev/telemetry-engine.git
cd telemetry-engine

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

*(Note: Ensure your `requirements.txt` includes `psutil`, `nvidia-ml-py`, `pytest`, and `PySide6`).*

---

## 🖥️ Running the Application

Launch the live telemetry dashboard stream directly from the console interface:

```bash
python3 main.py
```


---

## 🖥️ Expected Output Terminal UI

```text
====================================
      SYSTEM TELEMETRY ENGINE
====================================
[*] ENGINE MODE: High-Performance Linux Native (/proc)
------------------------------------
CPU Usage:                4.51%
------------------------------------
Total Memory:             7.42 GB
Used Memory:              2.97 GB
Available Memory:         4.45 GB
Memory Usage Percentage:  40.04%
====================================
         BATTERY TELEMETRY
====================================
Status:                   Not charging
Capacity:                 80%
Battery Health:           100.0%
====================================
         THERMAL TELEMETRY
====================================
CPU Temp:                 N/A (Max: N/A)
GPU [0]:                  NVIDIA GeForce RTX 4050 Laptop GPU
  Temp / Util:            49°C / 0%
  Power Draw:             14.26 W
====================================
          DISK TELEMETRY
====================================
Total Space:              1006.85 GB
Used Space:               5.6 GB
Free Space:               950.04 GB
------------------------------------
sdd:
  Read Speed:             492.53 MB/s
  Write Speed:            108.46 MB/s
====================================
         NETWORK TELEMETRY
====================================
eth0:
  Status:                 CONNECTED
  Download Speed:         14.66 Mbps
  Upload Speed:           1.25 Mbps
  Rx Errors/Drops:        0/0
  Tx Errors/Drops:        0/5
  Total Transferred:      1.57 GB
====================================

Press Ctrl+C to exit.
```

---

## 🧪 Testing Suite Matrix

The suite isolates production code behavior by injecting dynamically generated temporary file systems (`tmp_path`), mocking `subprocess.run` for sensors, mocking `pynvml` for GPU telemetry, and mocking `time.monotonic` for disk/network delta math.

```bash
pytest -v
```

### Coverage Blueprint (33 Passing Tests)

- **Mathematical Accuracy:** Verifies unit conversion paths and CPU/Disk/Network time delta operations.
- **Hardware Mocking:** Simulates `lm-sensors`, `pynvml`, `/proc/diskstats`, and `/proc/net/dev` across various hardware profiles.
- **Robustness Checks:** Forces edge situations including blank tracking paths, zero core totals, desktop battery fallbacks, bad integer parsing, and partition filtering.
- **Fault Tolerance:** Verifies that missing tools, malformed data, and hot-unplugged interfaces return specific error states rather than crashing.

---

## ⚠️ Known Limitations

As a systems-level engine interacting directly with hardware, behavior varies heavily by OS, kernel version, and hardware vendor. Here is what we explicitly know does not work or is restricted:

- **WSL (Windows Subsystem for Linux) Restrictions:** 
  - **Thermal Sensors:** WSL does not pass physical motherboard sensors through to the Linux kernel. CPU and Motherboard temperatures will safely fall back to `N/A`.
  - **Disk I/O & Network:** `/proc/diskstats` and `/proc/net/dev` inside WSL represent virtualized Hyper-V devices, not the physical Windows host hardware. Speeds are accurate to the virtualization layer.
  - **NVIDIA GPU:** `pynvml` may fail if the Windows host ASUS/Laptop software puts the dGPU to sleep (e.g., ASUS Eco Mode).
- **Laptop Fan Speeds (The Embedded Controller Trap):**
  - On almost all laptops, physical fans are controlled by the motherboard's Embedded Controller (EC). `pynvml` and `lm-sensors` will return `N/A` for laptop dGPU fans. This is a hardware restriction, not a software bug.
- **Cross-Platform Thermals (Windows/macOS):**
  - `psutil` does not expose CPU temperatures or fan speeds on Windows/macOS natively. Deep thermal telemetry is currently a Linux-only feature.
- **Disk Space Scope:**
  - The engine only monitors the primary root partition (`/` on Linux, `C:\` on Windows).
- **Optional System Dependencies:**
  - On Linux, deep CPU/Motherboard sensors require the `lm-sensors` package.
- **psutil Fallback Restrictions (Windows/macOS):**
  - The `psutil` fallback cannot read battery power draw or hardware health natively. It reports `0.0 W` and `100.0%` as placeholders.
  - `psutil.cpu_percent()` requires a baseline; it returns `0.0%` on the very first cycle.
