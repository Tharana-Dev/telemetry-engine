# Telemetry Engine

A high-performance, cross-platform system telemetry engine written in Python. It extracts deep system metrics by hooking directly into the Linux kernel virtual filesystem (`/proc` and `/sys`), and utilizes `psutil`, WMI, and `winreg` for deep hardware discovery on Windows. 

The CLI is built using `rich` and a non-blocking Producer/Consumer threading model, ensuring the UI renders smoothly at 4Hz regardless of hardware polling delays.

---

## 📅 Version History

| Version | Milestone | Key Additions |
| :--- | :--- | :--- |
| `v0.1.x` | Linux Core | Direct `/proc` parsing for CPU and Memory. Abstract Base Class (HAL). |
| `v0.2.x` | Battery & Thermal | ACPI battery parsing, NVML (`pynvml`) integration, `lm-sensors` JSON parsing. |
| `v0.3.x` | Disk & Network | `/proc/diskstats` and `/proc/net/dev` delta math. |
| `v0.5.x` | Unified Architecture | Replaced custom Enums with standard exceptions. Centralized error boundary. Rotating file logger. |
| `v0.9.x` | CLI & Threading | `rich.live` dashboard, dynamic progress bars, Producer/Consumer threading. |
| `v1.0.x` | Universal Engine | Complete Windows support via `psutil`, `wmi`, `winreg`, and `WinTmp`. Graceful privilege degradation. |

---

## 🔥 Key Features

- **Cross-Platform Hardware Abstraction Layer (HAL):** Built on an Abstract Base Class (ABC) contract. The UI asks for metrics without caring if the data comes from Linux kernel files, C-bindings, or Windows C-APIs.
- **Deep Hardware Discovery:** On Windows, uses `winreg` to extract the exact CPU model string and `wmi` to query the motherboard model and iGPU name—all without requiring Admin rights.
- **Linux Kernel-Direct Hooking:** Reads natively from `/proc/stat`, `/proc/meminfo`, `/proc/diskstats`, `/proc/net/dev`, and `/sys/class/power_supply/`.
- **Zero-Latency Thermal Caching:** NVML initialization is handled once in `__init__`, and `sensors` results are cached for 3 seconds. Cached thermal hits cost `~0.0008ms`.
- **Graceful Privilege Degradation:** On Windows, CPU temperature extraction (`WinTmp`) requires Administrator privileges. If run as a standard user, the engine logs a single warning, alerts the UI, and continues serving all other metrics perfectly.
- **Non-Blocking Threaded Architecture:** Hardware polling runs in a background daemon thread using `threading.Event` and `collections.deque`. The `rich` UI renders on the main thread at a fixed 1Hz.

---

## ⚠️ Known Limitations

- **Windows Thermal Sensors:** 
  - **Admin Required:** Windows blocks raw CPU MSR reads. `WinTmp` requires the terminal to be run as Administrator to read CPU temps. Without it, CPU Temp shows `N/A` (the UI indicates this).
  - **Core Isolation:** Windows Defender's Memory Integrity can block `WinTmp` from reading sensors entirely, even as Admin. The engine will safely fall back to `N/A`.
- **WSL (Windows Subsystem for Linux) Restrictions:**
  - **PCIe Hot-Plug:** WSL cannot hot-plug a GPU. If WSL boots while the dGPU is powered off (e.g., ASUS Eco Mode), `nvmlInit()` will fail until WSL is fully restarted.
- **Laptop Fan Speeds:** On almost all laptops, physical fans are controlled by the motherboard's Embedded Controller (EC). `pynvml` will correctly return `N/A` for laptop dGPU fans.
- **Disk Space Scope:** The engine only monitors the primary root partition (`/` on Linux, `C:\` on Windows).

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
│   ├── linux_*.py         # Linux-specific /proc and /sys parsers
│   ├── linux_sampler.py   # Linux adapter and unified error boundary
│   ├── psutil_sampler.py  # Universal cross-platform fallback driver
│   └── universal_impl/    # Windows/macOS implementation modules
│       ├── universal_cpu.py
│       ├── universal_memory.py
│       ├── universal_battery.py
│       ├── universal_thermal.py
│       ├── universal_disk.py
│       └── universal_network.py
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

## 🖥️ Expected Output (Windows)

When running on Windows, the engine uses the Universal HAL:
```text
 SYSTEM & HARDWARE                     I/O & NETWORK                 
 ─────────────────────────────         ───────────────────────────── 
 Engine Mode:  Windows (psutil)                                      
 Admin Mode:   No (CPU Temps Blocked)  DISK SPACE                    
                                         Total:      475.82 GB        
 CPU & MEMORY                            Used:       20.3% (96.7 GB)  
 CPU Usage:  ██████░░░░░░░░░░░ 77.8%      Free:       379.12 GB        
 Memory:     ███████░░░░░░░░░░ 74.1%                                  
                                       DISK I/O                      
 BATTERY                                 PhysicalDrive0:              
 Status:     Charging                      Read:  0.0 B/s            
 Capacity:   ████████████████ 80%           Write: 311.35 KB/s        
 Power:      N/A                                                     
 Time Est:   Wall Power (AC)           NETWORK                       
                                         WiFi: CONNECTED             
 THERMAL & GPU                             ↓ / ↑: 0.80 Kbps | 0.80 Kbps
 CPU:        AMD Ryzen 7 170 (3194 MHz)                                
 Motherboard:ASUSTeK COMPUTER INC. FA607NUQ                               
 iGPU:       AMD Radeon(TM) Graphics                                   
 CPU Temp:   Admin privileges required for CPU Temp
 GPU [0]:    NVIDIA GeForce RTX 4050 Laptop GPU
   54°C | 0% | 14.38W                     
```

## 🧪 Testing Suite Matrix

The suite isolates production code behavior by injecting dynamically generated temporary file systems (`tmp_path`), mocking `subprocess.run` for sensors, mocking `pynvml` for GPU telemetry, mocking `wmi` for battery health, and mocking `time.monotonic` for delta math.

```bash
pytest -v
```

### Coverage Blueprint (205+ Passing Tests)

- **Mathematical Accuracy:** Verifies unit conversion paths and time delta operations for both Linux `/proc` and `psutil`.
- **Hardware Mocking (Linux):** Simulates `lm-sensors`, `pynvml`, `/proc/diskstats`, and `/proc/net/dev` across various hardware profiles.
- **Hardware Mocking (Windows):** Simulates WMI battery health queries, WinTmp Admin restrictions, and Registry reads (`winreg`).
- **Robustness Checks:** Forces edge situations including blank tracking paths, zero core totals, desktop fallbacks, bad integer parsing, and partition filtering.
- **Fault Tolerance:** Verifies that missing tools, malformed data, and hot-unplugged interfaces return `None` or throw expected exceptions, which the Collector safely catches.
- **Threading:** Tests the `TelemetryWorker` thread start, stop, and buffer draining to ensure clean shutdowns without deadlocks.
- **Universal Edge Cases:** 30 dedicated tests for Windows modules covering WMI crashes, NVML loss mid-session, loopback filtering, and permission errors.
```