# Telemetry Engine

A high-performance, ultra-lightweight Linux system performance monitoring engine written in pure Python. It tracks real-time CPU consumption and memory profiles by hooking directly into core kernel data structures, completely avoiding the overhead of spawning subprocesses or installing heavy third-party framework dependencies.

---

## 🔥 Key Features

- **Zero-Dependency Architecture:** Written entirely in standard Python without relying on modules like `psutil`, ensuring an almost undetectable resource footprint.
- **Kernel-Direct Hooking:** Reads natively from `/proc/stat` and `/proc/meminfo` system pipelines to capture bare-metal statistics.
- **Defensive Error Handling:** Built with robust fault isolation. Empty file outputs, missing kernel keys, or system data anomalies safely return null-state fallback snapshots instead of raising fatal errors.
- **Test-Driven Design:** Leverages dependency injection (`stat_path` and `mem_path`), making the entire system completely testable without mocking core Python I/O modules.

---

## 🏗️ Project Layout

```text
telemetry-engine/
├── engine/
│   ├── __init__.py
│   ├── linux_cpu.py       # Direct parsing mechanics for kernel scheduling statistics
│   └── linux_memory.py    # Memory structural parser and metric translation units
├── tests/
│   ├── fixtures/
│   │   └── mock_meminfo.txt
|   |   └──mock_stat.txt
│   ├── test_cpu.py        
│   └── test_memory.py     
├── main.py                # Main executable application orchestrator run loop
├── README.md              # Documentation and architecture overview
└── requirements-dev.txt   # Test environment requirements (pytest, etc.)
```

---

## 🚀 Getting Started

### Prerequisites

- A Linux environment (Ubuntu, Debian, Fedora, RHEL, or WSL2 instances)
- Python 3.10 or higher

### 1. Environment Setup

Clone your repository, navigate to the directory, and initialize a sandboxed virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Development Dependencies

Install the comprehensive test suite framework:

```bash
pip install -r requirements-dev.txt
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
CPU Usage:                24.57%
------------------------------------
Total Memory:             15.42 GB
Used Memory:              6.14 GB
Available Memory:         9.28 GB
Memory Usage Percentage:  39.82%
====================================
Press Ctrl+C to exit.
```

> 💡 **Tip:** Press `Ctrl+C` inside the terminal window to trigger a clean, managed shutdown sequence.

---

## 🧪 Testing Suite Matrix

The suite isolates production code behavior from standard storage interfaces by injecting dynamically generated temporary file systems (`tmp_path`) for precision test tick management.

Run the test collection using the `pytest` binary runner:

```bash
pytest -v
```

### Coverage Blueprint

- **Mathematical Accuracy:** Verifies unit conversion paths (from Kilobytes up to Gigabytes via $1024^2$ scaling) and system time change operations.
- **Syntactical Resiliency:** Protects structural loops against arbitrary whitespace spacing, multi-indent layouts, or invalid non-colon configuration rows.
- **Robustness Checks:** Forces edge situations including completely blank tracking paths, zero core totals, and missing system key arrays to verify crash-prevention behavior.
