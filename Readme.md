# Telemetry Engine

A high-performance, cross-platform system telemetry engine written in Python. It extracts deep system metrics by hooking directly into the Linux kernel virtual filesystem (`/proc` and `/sys`), utilizing `nvidia-ml-py` for direct GPU driver access, and providing a graceful `psutil` fallback for Windows, macOS, and restricted environments.

The CLI is built using `rich` and a non-blocking Producer/Consumer threading model, ensuring the UI renders smoothly at 4Hz regardless of hardware polling delays.

---

## 📅 Version History

| Version | Milestone | Key Additions |
| :--- | :--- | :--- |
| `v0.1.x` | Linux Core | Direct `/proc` parsing for CPU and Memory. Abstract Base Class (HAL). |
| `v0.2.x` | Battery & Thermal | ACPI battery parsing, NVML (`pynvml`) integration, `lm-sensors` JSON parsing. |
| `v0.3.x` | Disk & Network | `/proc/diskstats` and `/proc/net/dev` delta math. |
| `v0.5.x` | Unified Architecture | Replaced custom Enums with standard Python exceptions. Centralized error boundary. Rotating file logger. |
| `v0.9.x` | CLI & Threading | `rich.live` dashboard, dynamic progress bars, Producer/Consumer threading, thread-safe `deque` buffers. |

---

## 🔥 Key Features

- **Cross-Platform Hardware Abstraction Layer (HAL):** Built on an Abstract Base Class (ABC) contract. The UI asks for metrics without caring if the data comes from Linux kernel files, C-bindings, or Windows C-APIs.
- **Linux Kernel-Direct Hooking:** Reads natively from `/proc/stat`, `/proc/meminfo`, `/proc/diskstats`, `/proc/net/dev`, and `/sys/class/power_supply/` to capture bare-metal statistics.
- **Zero-Latency Thermal Caching:** NVML initialization is handled once in `__init__`, and `sensors` results are cached for 3 seconds. Cached thermal hits cost `~0.0008ms`, eliminating subprocess blocking from the main loop.
- **Unified Exception Boundary:** Hardware queries are isolated. If a kernel file is missing, the sampler throws a standard exception. The `LinuxCollector` catches it, logs it to `telemetry.log`, and returns `None` to the UI.
- **Non-Blocking Threaded Architecture:** Hardware polling runs in a background daemon thread using `threading.Event` and `collections.deque`. The `rich` UI renders on the main thread at a fixed 1Hz, guaranteeing zero UI stuttering even during slow 2-second subprocess calls.

---

## ⚠️ Known Limitations

As a systems-level engine interacting directly with hardware, behavior varies heavily by OS, kernel version, and hardware vendor. These are the explicit limitations we have verified:

- **WSL (Windows Subsystem for Linux) Restrictions:**
  - **Thermal Sensors:** WSL does not pass physical motherboard sensors through to the Linux kernel. CPU and Motherboard temperatures will safely fall back to `N/A`.
  - **PCIe Hot-Plug:** WSL cannot hot-plug a GPU. If WSL boots while the dGPU is powered off (e.g., ASUS Eco Mode), `nvmlInit()` will fail until WSL is fully restarted (`wsl --shutdown`).
  - **Network:** WSL network interfaces represent virtualized Hyper-V switches, not the physical Wi-Fi or Ethernet card.
- **Laptop Fan Speeds:** On almost all laptops, physical fans are controlled by the motherboard's Embedded Controller (EC). `pynvml` will correctly return `N/A` for laptop dGPU fans.
- **Cross-Platform Thermals:** `psutil` does not expose CPU temperatures or fan speeds on Windows/macOS natively. Deep thermal telemetry is currently a Linux-only feature.
- **Windows Fallback (Pending):** The `psutil_sampler.py` currently has dummy implementations for Disk and Network metrics. Full Windows support is scheduled for the next phase.
- **Thermal Cold Start:** The very first thermal poll incurs a ~1.6s subprocess/NVML initialization cost. The cache handles all subsequent ticks instantly.

---

## 🏗️ Project Layout

```text
telemetry-engine/
├── cli/
│   ├── __init__.py
│   ├── dashboard.py       # Pure UI rendering (rich Tables, ProgressBars)
│   ├── data_collector.py  # Data layer orchestrator (gather_snapshots)
│   └── formatters.py      # Unit conversion and string formatting
├── engine/
│   ├── __init__.py
│   ├── base_sampler.py    # Abstract Base Class (HAL contract)
│   ├── models.py          # Dataclasses for strict type enforcement
│   ├── logger.py          # Rotating file logger configuration
│   ├── linux_cpu.py       # Direct parsing for kernel scheduling
│   ├── linux_memory.py    # Memory structural parser
│   ├── linux_battery.py   # ACPI/sysfs battery parsing
│   ├── linux_thermal.py   # NVML & lm-sensors JSON parsing
│   ├── linux_disk.py      # /proc/diskstats parsing & space telemetry
│   ├── linux_network.py   # /proc/net/dev parsing
│   ├── linux_sampler.py   # Linux adapter and unified error boundary
│   └── psutil_sampler.py  # Universal cross-platform fallback driver
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
├── main.py                # Entry point orchestrator & UI Thread
├── README.md              
└── requirements.txt       
```

---

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

---

## 🖥️ Running the Application

Launch the live `rich` dashboard directly from the terminal:

```bash
python3 main.py
```

### Expected Output Terminal UI

```text
                       SYSTEM TELEMETRY ENGINE                       
 ─────────────────────────────────────────────────────────────────── 
 SYSTEM & HARDWARE                     I/O & NETWORK                 
 ─────────────────────────────         ───────────────────────────── 
 Engine Mode:  Linux Native (/proc)                                  
                                       DISK SPACE                    
 CPU & MEMORY                            Total:      1006.85 GB       
 CPU Usage:  ███░░░░░░░░░░░░░░░░░ 13.3%  Used:       ░░░░░ 0.5% (5.18 GB)
 Memory:     █████████░░░░░░░░░░░ 44.7%  Free:       950.46 GB        
                                         
 BATTERY                               DISK I/O                      
 Status:     Not charging                sdd:                         
 Capacity:   ████████████████░░░░ 80%       Read:  1.84 MB/s           
 Power:      0.00 W                        Write: 7.91 KB/s           
 Time Est:   Wall Power (AC)                                          
                                       NETWORK                       
 THERMAL & GPU                           eth0 (CONNECTED)             
 CPU Temp:   N/A (Max: N/A)                ↓ / ↑: 97.74 Kbps | 150.97 Kbps
 GPU [0]:    NVIDIA GeForce RTX 4050       Rx Err/Drop: 0 / 0          
   46°C | N/A | 12.0W                     Tx Err/Drop: 0 / 0          
                                           Total Data:  478.26 KB     
 
 Press Ctrl+C to exit.
```

---

## 📊 Performance Benchmarks

The repository includes `benchmark.py`, an automated profiling script that measures execution time across all samplers.

### Optimization Results

| Sampler | Cold Start (First Tick) | Steady State (Cached) |
| :--- | :--- | :--- |
| CPU | 0.10 ms | 0.10 ms |
| Memory | 0.13 ms | 0.13 ms |
| Disk Space | 0.01 ms | 0.01 ms |
| Disk I/O | 0.22 ms | 0.22 ms |
| Network | 0.17 ms | 0.17 ms |
| **Thermal** | **~1,600 ms** | **0.0008 ms** |

*(Note: The cold start incurs the subprocess spawn and NVML init cost. The 3-second cache guarantees that the UI loop does not block on subsequent ticks. Every 3 seconds, a background subprocess is spawned, costing ~38ms).*

---

## 🧪 Testing Suite Matrix

The suite isolates production code behavior by injecting dynamically generated temporary file systems (`tmp_path`), mocking `subprocess.run` for sensors, mocking `pynvml` for GPU telemetry, and mocking `time.monotonic` for delta math.

```bash
pytest -v
```

### Coverage Blueprint (175 Passing Tests)

- **Mathematical Accuracy:** Verifies unit conversion paths and time delta operations.
- **Hardware Mocking:** Simulates `lm-sensors`, `pynvml`, `/proc/diskstats`, and `/proc/net/dev` across various hardware profiles.
- **Robustness Checks:** Forces edge situations including blank tracking paths, zero core totals, desktop fallbacks, bad integer parsing, and partition filtering.
- **Fault Tolerance:** Verifies that missing tools, malformed data, and hot-unplugged interfaces return `None` or throw expected exceptions, which the Collector safely catches.
- **Threading:** Tests the `TelemetryWorker` thread start, stop, and buffer draining to ensure clean shutdowns without deadlocks.
