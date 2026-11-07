"""
Tests for the telemetry-engine CLI.

Layout under test:
    main                 -> main()
    cli.data_collector   -> gather_snapshots(), TelemetryWorker
    cli.formatters       -> format_speed_bits, format_total_data,
                            format_disk_speed, format_disk_size

Strategy:
- Formatters and gather_snapshots get direct unit tests.
- main() is only tested for its *side effects* (which collector class
  was instantiated, whether a fallback occurred). It is never asked to
  render UI, and we never assert on visible dashboard strings — the
  Rich layout is an implementation detail and would couple every test
  to cosmetic changes.
- For the one iteration main() runs, Live / Console / TelemetryWorker
  are mocked and time.sleep raises KeyboardInterrupt immediately.
"""

import threading
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

# Entry point
from main import main

# Extracted modules
from cli.data_collector import gather_snapshots, TelemetryWorker
from cli.formatters import (
    format_disk_size,
    format_disk_speed,
    format_speed_bits,
    format_total_data,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _mk(**attrs):
    """MagicMock with explicit attributes set."""
    m = MagicMock()
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def _make_fake_collector():
    """A collector whose get_*() methods return plausible snapshots."""
    col = MagicMock()

    col.get_cpu_snapshot.return_value = _mk(usage_pct=42.0)
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


# ===========================================================================
# format_speed_bits
# ===========================================================================

def test_format_speed_bits_zero():
    assert format_speed_bits(0) == "0.00 Kbps"


def test_format_speed_bits_kbps_range():
    assert format_speed_bits(124_875) == "999.00 Kbps"


def test_format_speed_bits_boundary_1000_kbps_is_mbps():
    # Exactly 1000 Kbps expressed as 1.00 Mbps (networking convention)
    assert format_speed_bits(125_000) == "1.00 Mbps"


def test_format_speed_bits_mbps_range():
    assert format_speed_bits(1_250_000) == "10.00 Mbps"


def test_format_speed_bits_large():
    assert format_speed_bits(125_000_000) == "1000.00 Mbps"


# ===========================================================================
# format_total_data
# ===========================================================================

def test_format_total_data_bytes():
    assert format_total_data(0) == "0.00 Bytes"
    assert format_total_data(1023) == "1023.00 Bytes"


def test_format_total_data_boundary_1024_is_kb():
    assert format_total_data(1024) == "1.00 KB"


def test_format_total_data_kb_range():
    assert format_total_data(1024 * 500) == "500.00 KB"


def test_format_total_data_mb_range():
    assert format_total_data(1024 ** 2 * 5) == "5.00 MB"


def test_format_total_data_gb_range():
    assert format_total_data(1024 ** 3) == "1.00 GB"


def test_format_total_data_tb_range():
    assert format_total_data(1024 ** 4) == "1.00 TB"


def test_format_total_data_pb_overflow():
    assert format_total_data(1024 ** 5) == "1.00 PB"


# ===========================================================================
# format_disk_speed
# ===========================================================================

def test_format_disk_speed_none():
    assert format_disk_speed(None) == "N/A"


def test_format_disk_speed_negative():
    assert format_disk_speed(-1) == "N/A"


def test_format_disk_speed_bytes_range():
    assert format_disk_speed(0) == "0.0 B/s"
    assert format_disk_speed(512) == "512.0 B/s"


def test_format_disk_speed_kb_boundary():
    assert format_disk_speed(1024) == "1.00 KB/s"


def test_format_disk_speed_kb_range():
    assert format_disk_speed(1024 * 500) == "500.00 KB/s"


def test_format_disk_speed_mb_boundary():
    assert format_disk_speed(1024 ** 2) == "1.00 MB/s"


def test_format_disk_speed_mb_range():
    assert format_disk_speed(1_048_576) == "1.00 MB/s"
    assert format_disk_speed(5 * 1024 ** 2) == "5.00 MB/s"


def test_format_disk_speed_gb_boundary():
    assert format_disk_speed(1024 ** 3) == "1.00 GB/s"


def test_format_disk_speed_gb_range():
    assert format_disk_speed(2 * 1024 ** 3) == "2.00 GB/s"


# ===========================================================================
# format_disk_size
# ===========================================================================

def test_format_disk_size_none():
    assert format_disk_size(None) == "N/A"


def test_format_disk_size_negative():
    assert format_disk_size(-1) == "N/A"


def test_format_disk_size_bytes():
    assert format_disk_size(0) == "0.00 B"
    assert format_disk_size(1023) == "1023.00 B"


def test_format_disk_size_kb_boundary():
    assert format_disk_size(1024) == "1.00 KB"


def test_format_disk_size_mb():
    assert format_disk_size(1024 ** 2) == "1.00 MB"


def test_format_disk_size_gb():
    assert format_disk_size(1024 ** 3) == "1.00 GB"


def test_format_disk_size_tb():
    assert format_disk_size(1024 ** 4) == "1.00 TB"


def test_format_disk_size_pb_overflow():
    assert format_disk_size(1024 ** 5) == "1.00 PB"


# ===========================================================================
# gather_snapshots (data layer)
# ===========================================================================

def test_gather_snapshots_returns_all_subsystems():
    """Every get_*() call becomes a (result, None) entry."""
    snaps = gather_snapshots(_make_fake_collector())

    assert set(snaps) == {
        "cpu", "memory", "battery", "thermal",
        "disk_io", "disk_space", "network",
    }
    cpu, cpu_err = snaps["cpu"]
    assert cpu_err is None
    assert cpu.usage_pct == 42.0


def test_gather_snapshots_captures_exceptions():
    """A raised sampler call becomes (None, str(exc)); siblings unaffected."""
    collector = _make_fake_collector()
    collector.get_cpu_snapshot.side_effect = RuntimeError("boom")
    collector.get_network_snapshot.side_effect = PermissionError(13, "denied")

    snaps = gather_snapshots(collector)

    cpu, cpu_err = snaps["cpu"]
    assert cpu is None
    assert "boom" in cpu_err

    net, net_err = snaps["network"]
    assert net is None
    assert "denied" in net_err

    mem, mem_err = snaps["memory"]
    assert mem_err is None
    assert mem.used_pct == 50.0


def test_gather_snapshots_passes_through_none_and_empty():
    """None (no hardware) and [] (first tick) pass through unchanged."""
    collector = _make_fake_collector()
    collector.get_battery_snapshot.return_value = None
    collector.get_disk_io_snapshot.return_value = []

    snaps = gather_snapshots(collector)

    assert snaps["battery"] == (None, None)
    assert snaps["disk_io"] == ([], None)


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
    """Run main() for exactly one iteration. Returns the collector mocks so
    callers can assert which one was constructed."""
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
    """If LinuxCollector() raises, main() must construct PsutilCollector."""
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
    """main() must hand the collector, a deque buffer, and a stop event to
    TelemetryWorker, then start a thread running worker.run."""
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

    # Constructor: (data, buffer, stop_event, interval=...)
    args, kwargs = mock_worker_cls.call_args
    assert args[0] is collector
    assert isinstance(args[1], deque)
    assert isinstance(args[2], threading.Event)
    assert kwargs.get("interval") == 0.5


def test_main_sets_stop_event_on_keyboard_interrupt():
    """On Ctrl+C, main() must set the stop event and join the worker."""
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

    # The stop event passed to the worker must be set after Ctrl+C.
    stop_event = mock_worker_cls.call_args[0][2]
    assert stop_event.is_set()