# Telemetry Engine

A high-performance, cross-platform system telemetry engine written in Python. It extracts deep system metrics by hooking directly into the Linux kernel virtual filesystem (`/proc` and `/sys`), and utilizes `psutil`, WMI, and `winreg` for deep hardware discovery on Windows. 

The project features two frontends:
1. **CLI**: Built using `rich` and a non-blocking Producer/Consumer threading model, ensuring the UI renders smoothly at 4Hz regardless of hardware polling delays.
2. **GUI**: Built with `PySide6` and `pyqtgraph`, featuring a cyberpunk-inspired, dynamically themed dark-mode interface with 60FPS live graphs and zero-latency data decoupling.

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
| `v1.1.x` | **UI Architecture** | PySide6 GUI overhaul. Extracted reusable `LiveGraph` and `StatCard` widgets. Dual-timer data fetching. Dynamic accent theming. |

---

## 🔥 Key Features

### Backend & Architecture
- **Cross-Platform Hardware Abstraction Layer (HAL):** Built on an Abstract Base Class (ABC) contract. The UI asks for metrics without caring if the data comes from Linux kernel files, C-bindings, or Windows C-APIs.
- **Deep Hardware Discovery:** On Windows, uses `winreg` to extract the exact CPU model string and `wmi` to query the motherboard model and iGPU name—all without requiring Admin rights.
- **Linux Kernel-Direct Hooking:** Reads natively from `/proc/stat`, `/proc/meminfo`, `/proc/diskstats`, `/proc/net/dev`, and `/sys/class/power_supply/`.
- **Graceful Privilege Degradation:** On Windows, CPU temperature extraction (`WinTmp`) requires Administrator privileges. If run as a standard user, the engine logs a single warning, alerts the UI, and continues serving all other metrics perfectly.
- **WMI Fallback for AMD:** If `WinTmp` fails to read CPU temps on older AMD Ryzen chips, the engine seamlessly falls back to the Windows ACPI Thermal Zone via WMI.

### User Interface (GUI)
- **Dual-Timer Decoupling:** The UI uses two independent timers. A 30ms timer renders graphs at 60FPS, while a 1000ms timer updates the text `StatCards` exactly once per second, preventing flickering and saving CPU cycles.
- **Reusable Component Library:** Extracted `LiveGraph` (PyQtGraph) and `StatCard` widgets, allowing rapid development of new hardware pages without duplicating QSS or layout code.
- **Dynamic Theming Engine:** A singleton `Personalization` module broadcasts signals when the user changes the accent color. Every SVG, graph pen, and text highlight repaints instantly.
- **Zero-Garbage-Collection Crashes:** Graph widgets are bound to class scope (rather than factory functions) to prevent PySide6 C++ memory pointers from being prematurely destroyed.
- **Thread-Safe Data Pipeline:** Background workers poll hardware at 10Hz, pushing data into a thread-safe `deque`. The UI thread safely drains the queue without blocking the event loop.

---

## ⚠️ Known Limitations

- **Windows Thermal Sensors:** 
  - **Admin Required:** Windows blocks raw CPU MSR reads. `WinTmp` requires the terminal to be run as Administrator to read CPU temps. Without it, CPU Temp shows `--` (the UI explicitly shows "Admin Required").
  - **Core Isolation:** Windows Defender's Memory Integrity can block `WinTmp` from reading sensors entirely, even as Admin. The engine will safely fall back to WMI or `N/A`.
  - **Antivirus Flags:** `WinTmp` uses the `WinRing0` driver, which Windows Defender often flags as a vulnerable driver (CVE-2020-14979). For development, a folder exclusion is required.
- **WSL (Windows Subsystem for Linux) Restrictions:**
  - **PCIe Hot-Plug:** WSL cannot hot-plug a GPU. If WSL boots while the dGPU is powered off (e.g., ASUS Eco Mode), `nvmlInit()` will fail until WSL is fully restarted.
- **Laptop Fan Speeds:** On almost all laptops, physical fans are controlled by the motherboard's Embedded Controller (EC). `pynvml` will correctly return `N/A` for laptop dGPU fans.
- **Disk Space Scope:** The engine only monitors the primary root partition (`/` on Linux, `C:\` on Windows).

---

## 🏗️ Project Layout

```text
telemetry-engine/
├── cli/                       # CLI Application (Phase 1)
│   ├── __init__.py
│   ├── dashboard.py           # Pure UI rendering (rich Tables, ProgressBars)
│   ├── data_collector.py      # Data layer orchestrator (gather_snapshots)
│   └── formatters.py          # Unit conversion and string formatting
├── engine/                    # Core Hardware Engine
│   ├── __init__.py
│   ├── base_sampler.py        # Abstract Base Class (HAL contract)
│   ├── models.py              # Dataclasses for strict type enforcement
│   ├── logger.py              # Rotating file logger configuration
│   ├── linux_*.py             # Linux-specific /proc and /sys parsers
│   ├── linux_sampler.py       # Linux adapter and unified error boundary
│   ├── psutil_sampler.py      # Universal cross-platform fallback driver
│   └── universal_impl/        # Windows/macOS implementation modules
│       ├── universal_cpu.py
│       ├── universal_memory.py
│       ├── universal_battery.py
│       ├── universal_thermal.py
│       ├── universal_disk.py
│       └── universal_network.py
├── ui/                        # PySide6 GUI Application (Phase 2)
│   ├── data/                  # Background QThread workers (CPU, Mem, Net)
│   ├── pages/                 # UI Pages (Dashboard, CPU, Memory, Network)
│   ├── widgets/               # Reusable components (LiveGraph, StatCard)
│   ├── theme.py               # Global QSS stylesheets and color palettes
│   ├── personalization.py     # Accent color singleton and monogram logic
│   ├── sidebar.py             # Navigation bar and accent swatches
│   ├── launchpad_panel.py     # Home page guide and admin status
│   └── identity_panel.py      # Home page hardware specs card
├── tests/                     # 205+ Pytest unit tests
├── app.manifest               # UAC Admin elevation for Nuitka compilation
├── benchmark.py               # Automated performance profiler
├── gui.py                     # GUI Entry point
├── main.py                    # CLI Entry point
├── README.md              
└── requirements.txt       
```

---

## 🖥️ Expected Output (GUI Architecture)

The GUI features a persistent left sidebar for navigation and dynamic accent colors. The pages are structured as follows:

*   **Home**: User greeting, WinTmp Admin status, hardware specs, and an interactive "About & System Guide" explaining how to read the graphs.
*   **Dashboard**: A 3x2 grid of `StatCard`s showing live CPU, Memory, GPU, Battery, Disk, and Network telemetry.
*   **CPU**: Two 60FPS `LiveGraph`s (Utilization & Frequency) and two `StatCard`s (Processor Info & Live Metrics with Max Temp tracking).
*   **Memory**: Two `LiveGraph`s (Utilization & Allocation) and two `StatCard`s (Overview & Details).
*   **Network**: Two `LiveGraph`s (Download & Upload speed) with dynamic Y-axis scaling, and three `StatCard`s (Connection, Live Traffic, Link Quality).

---

## 🖥️ Expected Output (CLI - Windows)

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

---

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

---

### Optimization Results (Windows Fallback)

| Sampler | Cold Start / First Tick | Steady State | Notes |
| :--- | :--- | :--- | :--- |
| CPU | 0.78 ms | 0.78 ms | `psutil.cpu_percent` |
| Memory | 0.10 ms | 0.10 ms | `psutil.virtual_memory` |
| Disk Space | 0.10 ms | 0.10 ms | `psutil.disk_usage` |
| Disk I/O | 0.15 ms | 0.15 ms | `psutil.disk_io_counters` |
| **Network** | **36.7 ms** | **36.7 ms** | Slow due to enumerating all Windows virtual adapters. Handled safely by the background thread. |
| **Thermal** | **~1585 ms** | **~3.6 ms** | WinTmp cold start. Cached by the background thread. |

*(Note: The 3.8ms target was for synchronous execution. Because hardware polling runs in isolated background `QThreads` in the GUI, latencies up to 500ms have zero impact on UI frame rate).*
