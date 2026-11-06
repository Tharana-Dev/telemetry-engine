# Telemetry Engine

A high-performance, system telemetry engine written in Python. The Linux engine is fully functional, extracting deep system metrics directly from the kernel virtual filesystem (`/proc` and `/sys`), utilizing `nvidia-ml-py` for direct GPU driver access, and implementing advanced fault tolerance. 

**Note:** The cross-platform (`psutil`) driver for Windows and macOS is currently a **stub (dummy implementation)** and is the next phase of development. Deep thermal and hardware metrics are currently Linux-only.

---

## 🔥 Key Features (Linux)

- **Cross-Platform Hardware Abstraction Layer (HAL):** Built on an Abstract Base Class (ABC) contract. The UI asks for metrics via the contract without knowing *how* they are fetched.
- **Linux Kernel-Direct Hooking:** Reads natively from `/proc/stat`, `/proc/meminfo`, `/proc/diskstats`, `/proc/net/dev`, and `/sys/class/power_supply/` to capture bare-metal statistics.
- **Zero-Latency Thermal Caching:** NVML initialization is handled once in `__init__`, and `sensors` results are cached for 3 seconds. Cached thermal hits cost `~0.0008ms`, eliminating subprocess blocking from the main loop.
- **Direct GPU Telemetry via NVML:** Supports multi-GPU setups using a `GpuInfo` dataclass, queries temperature, utilization, and power draw directly from the driver, and handles laptop Embedded Controller (EC) fan restrictions.
- **Resilient Battery Diagnostics:** Calculates real-time power draw (Watts), time remaining, and hardware degradation (Health %), with fallbacks for both `energy_*` and `charge_*` sysfs paths.
- **Unified Exception Boundary:** Samplers throw standard exceptions (e.g., `FileNotFoundError`) or return `None` for partial failures. The `LinuxCollector` catches all exceptions at the boundary, ensuring one failing hardware component never crashes the entire dashboard.

---

## ⚠️ Known Limitations

- **Cross-Platform Support is a Stub:** Windows and macOS currently use a dummy `PsutilCollector`. It does not yet implement the full HAL contract for disk, network, or thermal metrics. This is the next development milestone.
- **WSL (Windows Subsystem for Linux) Restrictions:** 
  - **Thermal Sensors:** WSL does not pass physical motherboard sensors through to the Linux kernel.
  - **Network:** WSL network interfaces (`eth0`) represent virtualized Hyper-V switches.
- **Laptop Fan Speeds:** On almost all laptops, physical fans are controlled by the motherboard's Embedded Controller (EC). `pynvml` will return `N/A` for laptop dGPU fans.
- **Cross-Platform Thermals:** `psutil` does not expose CPU temperatures or fan speeds on Windows/macOS natively. Deep thermal telemetry is currently a Linux-only feature.
- **Disk Space Scope:** The engine only monitors the primary root partition (`/` on Linux, `C:\` on Windows).

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
│   ├── linux_disk.py      # /proc/diskstats parsing & space telemetry
│   ├── linux_network.py   # /proc/net/dev parsing
│   ├── linux_sampler.py   # Linux adapter bridging the HAL to raw parsers
│   └── psutil_sampler.py  # Universal cross-platform fallback (Stub)
├── tests/
│   ├── fixtures/
│   ├── test_cpu.py        
│   ├── test_memory.py
│   ├── test_battery.py
│   ├── test_linux_thermals.py
│   ├── test_linux_disk.py
│   ├── test_linux_network.py
│   ├── test_main.py
│   └── test_psutil.py
├── benchmark.py           # Automated performance profiler
├── main.py                # Main executable orchestrator
├── README.md              
└── requirements.txt       
```

---

## 🚀 Getting Started

### Prerequisites

- **OS:** Linux (Ubuntu, Debian, Fedora, RHEL, or WSL2).
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

---

## 🖥️ Running the Application

Launch the live telemetry dashboard stream directly from the console interface:

```bash
python3 main.py
```

### Expected Output Terminal UI

```text
╔══════════════════════════════════════════════════════════════════╤══════════════════════════════════════════════════════════════════╗
║ SYSTEM & HARDWARE                                                │ I/O & NETWORK                                                    ║
║ ─────────────────────────────                                    │ ─────────────────────────────                                    ║
║ Engine Mode:  Linux Native (/proc)                               │                                                                  ║
║                                                                  │ DISK SPACE                                                       ║
║ CPU & MEMORY                                                     │   Total:      1006.85 GB                                         ║
║   CPU Usage:  4.03%                                              │   Used:       5.20 GB  (0.5%)                                    ║
║   Memory:     35.37% (2.62 GB / 7.42 GB)                         │   Free:       950.43 GB                                          ║
║                                                                  │                                                                  ║
║ BATTERY                                                          │ DISK I/O                                                         ║
║   Status:     Discharging                                        │   sdd:                                                           ║
║   Capacity:   80%  (Health: 100.0%)                              │     Read:  492.53 MB/s                                           ║
║   Power:      1.20 W                                             │     Write: 108.46 MB/s                                           ║
║   Time Est:   3h 20m remaining                                   │                                                                  ║
║                                                                  │ NETWORK                                                          ║
║ THERMAL & GPU                                                    │   eth0 (CONNECTED)                                               ║
║   CPU Temp:   N/A (Max: N/A)                                     │     ↓ 1.95 Mbps | ↑ 2.76 Mbps                                    ║
║   GPU [0]:    NVIDIA GeForce RTX 4050 Laptop GPU                 │     Total Rx Err/Drop: 0 / 0                                     ║
║     49°C | 0% | 14.26W                                           │     Total Tx Err/Drop: 0 / 0                                     ║
║                                                                  │     Total Data:  929.42 MB                                       ║
╚══════════════════════════════════════════════════════════════════╧══════════════════════════════════════════════════════════════════╝

 Press Ctrl+C to exit.
```

---

## 📊 Performance Benchmarks

The repository includes `benchmark.py`, an automated profiling script that measures execution time (`time.perf_counter_ns`) and memory allocations (`tracemalloc`) across all samplers.

```bash
python3 benchmark.py
```

### Optimization Results
By moving `pynvml.nvmlInit()` to the constructor and implementing a 3-second cache on thermal reads, the most dangerous bottleneck was eliminated:

| Sampler | Pre-Optimization Avg | Post-Optimization Avg (Cached) |
| :--- | :--- | :--- |
| CPU | 0.09 ms | 0.10 ms |
| Memory | 0.12 ms | 0.13 ms |
| Disk Space | 0.01 ms | 0.01 ms |
| Disk I/O | 0.22 ms | 0.22 ms |
| Network | 0.11 ms | 0.17 ms |
| **Thermal** | **166.34 ms** | **0.0008 ms** |

---

## 🧪 Testing Suite Matrix

The suite isolates production code behavior by injecting dynamically generated temporary file systems (`tmp_path`), mocking `subprocess.run` for sensors, mocking `pynvml` for GPU telemetry, and mocking `time.monotonic` for delta math.

```bash
pytest -v
```

### Coverage Blueprint (208 Passing Tests)

- **Mathematical Accuracy:** Verifies unit conversion paths and time delta operations.
- **Hardware Mocking:** Simulates `lm-sensors`, `pynvml`, `/proc/diskstats`, and `/proc/net/dev` across various hardware profiles.
- **Robustness Checks:** Forces edge situations including blank tracking paths, zero core totals, desktop fallbacks, bad integer parsing, and partition filtering.
- **Fault Tolerance:** Verifies that missing tools, malformed data, and hot-unplugged interfaces return specific error states or fallbacks rather than crashing.
- **UI Rendering:** Tests the terminal UI string generation (`print_side_by_side`) to ensure edge cases (like a CONNECTING interface) do not crash the render loop.

---

## 📝 Logging & Error Handling

The engine uses Python's built-in `logging` module with a `RotatingFileHandler`. 

- **Silent UI Boundary:** All exceptions (both at initialization and runtime) are caught by the `LinuxCollector` boundary. This ensures one broken sensor never crashes the dashboard. The UI simply displays `Unavailable` or `N/A`.
- **The Flight Recorder:** When an exception is caught, the exact traceback and error message are written to `telemetry.log`. 
- **Log Rotation:** The log file rotates at 1MB, keeping up to 5 historical backups (`telemetry.log.1` through `telemetry.log.5`) to prevent filling up the hard drive.
- **Console Cleanliness:** Errors are never printed to the console. This keeps the terminal UI clean and prevents the dashboard from scrolling.

To inspect the exact reason a sensor failed, open the log file:
```bash
cat telemetry.log