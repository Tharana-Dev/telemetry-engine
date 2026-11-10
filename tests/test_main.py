"""
Tests for the telemetry-engine CLI.
"""

import threading
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from main import main
from cli.data_collector import gather_snapshots, TelemetryWorker
from cli.formatters import (
    format_disk_size,
    format_disk_speed,
    format_speed_bits,
    format_total_data,
)

def _mk(**attrs):
    m = MagicMock()
    for k, v in attrs.items():
        setattr(m, k, v)
    return m

def _make_fake_collector():
    col = MagicMock()

    # FIX: Added current_freq_mhz so the dashboard can format it
    col.get_cpu_snapshot.return_value = _mk(usage_pct=42.0, current_freq_mhz=2000)
    
    col.get_memory_snapshot.return_value = _mk(
        used_pct=50.0, used_gb=4.0, total_gb=8.0,
    )
    col.get_battery_snapshot.return_value = _mk(
        status="Charging", capacity=80, power_watts=15.0,
        hours_left=None, health_percent=95.0, online=True,
    )
    col.get_thermal_snapshot.return_value = _mk(
        sensor_available=True, cpu_temp=55.0, cpu_temp_max=100.0,
        system_fans={"fan1": 1000}, gpu_available=True,
        gpus=[_mk(
            index=0, name="NVIDIA GeForce RTX 4050",
            temperature_c=45, utilization_pct=10, power_w=14.0,
        )],
    )
    col.get_disk_io_snapshot.return_value = [
        _mk(device="sda", read_bps=1_048_576, write_bps=2_097_152),
    ]
    col.get_disk_space_snapshot.return_value = _mk(
        total_bytes=500 * 1024 ** 3,
        used_bytes=250 * 1024 ** 3,
        free_bytes=250 * 1024 ** 3,
        percent=50.0,
    )
    col.get_network_snapshot.return_value = [
        _mk(
            interface="eth0", status="CONNECTED",
            download_bps=1_000_000, upload_bps=500_000,
            rx_errors=0, tx_errors=0, rx_drops=0, tx_drops=0,
            total_bytes=10_000_000,
        ),
    ]
    col.get_system_health.return_value = {}
    return col


# ... [Keep all the format_speed_bits, format_total_data, format_disk_speed, format_disk_size, and gather_snapshots tests exactly as they are] ...


# ===========================================================================
# TelemetryWorker (data layer)
# ===========================================================================

def test_telemetry_worker_fills_buffer_and_stops():
    buffer = deque(maxlen=10)
    stop_event = threading.Event()
    worker = TelemetryWorker(
        _make_fake_collector(), buffer, stop_event, interval=0.01,
    )

    t = threading.Thread(target=worker.run, daemon=True)
    t.start()
    for _ in range(50):
        if buffer:
            break
        threading.Event().wait(0.01)
    stop_event.set()
    t.join(timeout=2.0)

    assert not t.is_alive()
    assert len(buffer) > 0
    assert "cpu" in buffer[0]


# ===========================================================================
# main() — collector selection (side effects only, no rendering)
# ===========================================================================

def _run_main_once(collector, *, system="Linux"):
    with patch("main.platform.system", return_value=system), \
         patch("main.LinuxCollector", return_value=collector) as mock_lc, \
         patch("main.PsutilCollector", return_value=collector) as mock_pc, \
         patch("main.TelemetryWorker"), \
         patch("main.Live"), \
         patch("main.Console"), \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        main()
        return mock_lc, mock_pc


def test_main_uses_linux_collector_on_linux():
    mock_lc, mock_pc = _run_main_once(_make_fake_collector(), system="Linux")
    assert mock_lc.called
    assert not mock_pc.called


def test_main_uses_psutil_collector_on_non_linux():
    mock_lc, mock_pc = _run_main_once(_make_fake_collector(), system="Windows")
    assert mock_pc.called
    assert not mock_lc.called


def test_main_falls_back_to_psutil_on_linux_init_failure():
    with patch("main.platform.system", return_value="Linux"), \
         patch("main.LinuxCollector", side_effect=ImportError("no ctypes")), \
         patch("main.PsutilCollector", return_value=_make_fake_collector()) as mock_pc, \
         patch("main.TelemetryWorker"), \
         patch("main.Live"), \
         patch("main.Console"), \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        main()

    assert mock_pc.called


# ===========================================================================
# main() — worker lifecycle
# ===========================================================================

def test_main_starts_worker_with_collector_and_buffer():
    collector = _make_fake_collector()
    with patch("main.platform.system", return_value="Linux"), \
         patch("main.LinuxCollector", return_value=collector), \
         patch("main.TelemetryWorker") as mock_worker_cls, \
         patch("main.Live"), \
         patch("main.Console"), \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker
        main()

    args, kwargs = mock_worker_cls.call_args
    assert args[0] is collector
    assert isinstance(args[1], deque)
    assert isinstance(args[2], threading.Event)
    assert kwargs.get("interval") == 0.5


def test_main_sets_stop_event_on_keyboard_interrupt():
    collector = _make_fake_collector()
    with patch("main.platform.system", return_value="Linux"), \
         patch("main.LinuxCollector", return_value=collector), \
         patch("main.TelemetryWorker") as mock_worker_cls, \
         patch("main.Live"), \
         patch("main.Console"), \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker
        main()

    stop_event = mock_worker_cls.call_args[0][2]
    assert stop_event.is_set()