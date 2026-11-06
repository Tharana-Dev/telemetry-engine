"""
Tests for main.py — the CLI dashboard.

Strategy:
- Pure helpers (format_*, print_side_by_side) get unit-level coverage.
- gather_snapshots (data layer) is tested with fake collectors.
- build_dashboard (UI layer) is tested as a pure function against synthetic
  snapshot dicts — it must never touch a collector.
- main() runs exactly one iteration via time.sleep -> KeyboardInterrupt,
  then capsys is asserted for the rendered view.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from main import (
    build_dashboard,
    format_disk_size,
    format_disk_speed,
    format_speed_bits,
    format_total_data,
    gather_snapshots,
    main,
    print_side_by_side,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _mk(**attrs):
    """MagicMock with explicit attributes set — avoids kwarg-vs-behavior
    ambiguity and makes each field visible to a reader."""
    m = MagicMock()
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def _make_fake_collector():
    """A collector whose get_*() methods return plausible snapshots.

    All values chosen so their formatted strings are greppable:
    42.0%, 4.00 GB / 8.00 GB, 500.00 GB, 1.00 MB/s, 8.00 Mbps, etc.
    """
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

    # Empty health map -> no degraded subsystems on the banner.
    col.get_system_health.return_value = {}
    return col


def _run_main_once(collector, *, system="Linux"):
    """Run main() for exactly one iteration.

    time.sleep is patched to raise KeyboardInterrupt on the first call,
    which main() catches internally — so no exception escapes.
    """
    with patch("main.platform.system", return_value=system), \
         patch("main.os.system"), \
         patch("main.shutil.get_terminal_size") as ts, \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        ts.return_value = os.terminal_size((200, 40))
        if system == "Linux":
            with patch("main.LinuxCollector", return_value=collector):
                main()
        else:
            with patch("main.PsutilCollector", return_value=collector):
                main()


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
# print_side_by_side
# ===========================================================================

def test_print_side_by_side_renders_box_and_content(capsys):
    with patch("main.shutil.get_terminal_size") as ts:
        ts.return_value = os.terminal_size((120, 24))
        print_side_by_side(["LEFT"], ["RIGHT"])

    out = capsys.readouterr().out
    assert "╔" in out and "╗" in out
    assert "╚" in out and "╝" in out
    assert "╤" in out and "╧" in out
    assert "LEFT" in out
    assert "RIGHT" in out


def test_print_side_by_side_pads_shorter_column(capsys):
    with patch("main.shutil.get_terminal_size") as ts:
        ts.return_value = os.terminal_size((120, 24))
        print_side_by_side(["a"], ["1", "2", "3"])

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 5  # header + 3 body + footer
    assert "a" in lines[1]
    assert "2" in lines[2]
    assert "3" in lines[3]


def test_print_side_by_side_wraps_long_lines(capsys):
    """A line longer than the effective column width should wrap, not overflow.

    Note: print_side_by_side enforces a minimum term_width of 80 (so the box
    never collapses on small terminals). At width 80, left_width is 36, so
    the test string must exceed 36 chars to actually force a wrap.
    """
    long_text = (
        "This is a very long line that must wrap because it is longer "
        "than the column width"
    )
    assert len(long_text) > 36  # guard: the premise of this test

    with patch("main.shutil.get_terminal_size") as ts:
        ts.return_value = os.terminal_size((80, 24))
        print_side_by_side([long_text], ["short"])

    lines = capsys.readouterr().out.splitlines()
    # 2 borders + N body lines where N >= 2 (wrap happened)
    assert len(lines) > 3
    # Sanity check: some fragment of the string was rendered
    joined = "\n".join(lines)
    assert "This is a very long" in joined


def test_print_side_by_side_handles_empty_lines(capsys):
    with patch("main.shutil.get_terminal_size") as ts:
        ts.return_value = os.terminal_size((120, 24))
        print_side_by_side(["a", "", "b"], ["1", "", "3"])

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 5


# ===========================================================================
# gather_snapshots (DATA LAYER)
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

    # Neighbours are untouched.
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
# build_dashboard (UI LAYER — pure function)
# ===========================================================================

def _fake_snapshots(**overrides):
    """Complete snapshots dict for build_dashboard; per-key overridable."""
    base = {
        "cpu": (_mk(usage_pct=42.0), None),
        "memory": (_mk(used_pct=50.0, used_gb=4.0, total_gb=8.0), None),
        "battery": (_mk(
            status="Charging", capacity=80, power_watts=15.0,
            hours_left=None, health_percent=95.0, online=True,
        ), None),
        "thermal": (_mk(
            sensor_available=True, cpu_temp=55.0, cpu_temp_max=100.0,
            system_fans={"fan1": 1000}, gpu_available=True,
            gpus=[_mk(index=0, name="GPU", temperature_c=45,
                      utilization_pct=10, power_w=14.0)],
        ), None),
        "disk_io": ([_mk(device="sda", read_bps=1_048_576, write_bps=2_097_152)], None),
        "disk_space": (_mk(
            total_bytes=500 * 1024 ** 3,
            used_bytes=250 * 1024 ** 3,
            free_bytes=250 * 1024 ** 3, percent=50.0,
        ), None),
        "network": ([_mk(
            interface="eth0", status="CONNECTED",
            download_bps=1_000_000, upload_bps=500_000,
            rx_errors=0, tx_errors=0, rx_drops=0, tx_drops=0,
            total_bytes=10_000_000,
        )], None),
    }
    base.update(overrides)
    return base


def test_build_dashboard_is_pure():
    """Same snapshots -> identical output on repeated calls."""
    snaps = _fake_snapshots()
    a = build_dashboard(snaps, "Linux", False, None, [])
    b = build_dashboard(snaps, "Linux", False, None, [])
    assert a == b


def test_build_dashboard_renders_from_snapshots_only():
    """build_dashboard accepts a plain dict; no collector involved."""
    left, right = build_dashboard(_fake_snapshots(), "Linux", False, None, [])

    assert any("SYSTEM & HARDWARE" in line for line in left)
    assert any("42.0%" in line for line in left)
    assert any("500.00 GB" in line for line in right)
    assert any("eth0 (CONNECTED)" in line for line in right)


# ===========================================================================
# main() — happy path & mode selection
# ===========================================================================

def test_main_happy_path_linux_renders_all_sections(capsys):
    _run_main_once(_make_fake_collector(), system="Linux")
    out = capsys.readouterr().out

    for header in (
        "SYSTEM & HARDWARE", "CPU & MEMORY", "BATTERY",
        "THERMAL & GPU", "I/O & NETWORK", "DISK SPACE", "DISK I/O", "NETWORK",
    ):
        assert header in out

    assert "Linux Native (/proc)" in out
    assert "42.0%" in out
    assert "50.0%" in out
    assert "4.00 GB / 8.00 GB" in out
    assert "eth0 (CONNECTED)" in out


def test_main_prints_initializing_splash(capsys):
    """The very first screen is an 'Initializing...' message, not a blank box."""
    _run_main_once(_make_fake_collector(), system="Linux")
    out = capsys.readouterr().out
    assert "Initializing... gathering first samples" in out


def test_main_prints_exit_message_on_keyboard_interrupt(capsys):
    _run_main_once(_make_fake_collector(), system="Linux")
    out = capsys.readouterr().out
    assert "Press Ctrl+C to exit" in out
    assert "Program interrupted" in out


def test_main_uses_linux_collector_on_linux(capsys):
    collector = _make_fake_collector()
    with patch("main.platform.system", return_value="Linux"), \
         patch("main.LinuxCollector", return_value=collector) as mock_lc, \
         patch("main.PsutilCollector") as mock_pc, \
         patch("main.os.system"), \
         patch("main.shutil.get_terminal_size") as ts, \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        ts.return_value = os.terminal_size((200, 40))
        main()

    assert mock_lc.called
    assert not mock_pc.called


def test_main_uses_psutil_collector_on_non_linux(capsys):
    collector = _make_fake_collector()
    with patch("main.platform.system", return_value="Windows"), \
         patch("main.LinuxCollector") as mock_lc, \
         patch("main.PsutilCollector", return_value=collector) as mock_pc, \
         patch("main.os.system"), \
         patch("main.shutil.get_terminal_size") as ts, \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        ts.return_value = os.terminal_size((200, 40))
        main()

    assert mock_pc.called
    assert not mock_lc.called
    assert "Windows (psutil)" in capsys.readouterr().out


def test_main_falls_back_to_psutil_on_global_init_failure(capsys):
    collector = _make_fake_collector()
    with patch("main.platform.system", return_value="Linux"), \
         patch("main.LinuxCollector", side_effect=ImportError("no ctypes")), \
         patch("main.PsutilCollector", return_value=collector), \
         patch("main.os.system"), \
         patch("main.shutil.get_terminal_size") as ts, \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        ts.return_value = os.terminal_size((200, 40))
        main()

    out = capsys.readouterr().out
    assert "FALLBACK (ImportError)" in out


def test_main_shows_degraded_banner(capsys):
    """Non-None entries in get_system_health() become the 'Missing:' list."""
    collector = _make_fake_collector()
    collector.get_system_health.return_value = {
        "battery": "PermissionError: denied",
        "thermal": None,
    }
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "Linux Native (degraded)" in out
    assert "Missing:" in out
    assert "battery" in out


# ===========================================================================
# main() — per-subsystem exception rendering
# ===========================================================================

def test_main_cpu_exception_shows_unavailable(capsys):
    collector = _make_fake_collector()
    collector.get_cpu_snapshot.side_effect = RuntimeError("boom")
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "CPU Usage:  Unavailable" in out
    assert "50.0%" in out  # memory still renders


def test_main_memory_exception_shows_unavailable(capsys):
    collector = _make_fake_collector()
    collector.get_memory_snapshot.side_effect = RuntimeError("boom")
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "Memory:     Unavailable" in out


# ===========================================================================
# main() — battery branches
# ===========================================================================

def test_main_battery_none_shows_not_detected(capsys):
    collector = _make_fake_collector()
    collector.get_battery_snapshot.return_value = None
    _run_main_once(collector, system="Linux")

    assert "Not Detected" in capsys.readouterr().out


def test_main_battery_error_shows_unavailable(capsys):
    collector = _make_fake_collector()
    collector.get_battery_snapshot.side_effect = RuntimeError("boom")
    _run_main_once(collector, system="Linux")

    assert "Status:     Unavailable" in capsys.readouterr().out


def test_main_battery_health_zero_renders_as_zero_percent(capsys):
    """health_percent=0.0 must render '0.0%', not 'N/A'."""
    collector = _make_fake_collector()
    collector.get_battery_snapshot.return_value = _mk(
        status="Discharging", capacity=5, power_watts=10.0,
        hours_left=0.1, health_percent=0.0, online=False,
    )
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "0.0%" in out
    assert "Health: N/A" not in out


def test_main_battery_health_none_renders_na(capsys):
    collector = _make_fake_collector()
    collector.get_battery_snapshot.return_value = _mk(
        status="Charging", capacity=80, power_watts=15.0,
        hours_left=None, health_percent=None, online=True,
    )
    _run_main_once(collector, system="Linux")

    assert "Health: N/A" in capsys.readouterr().out


def test_main_battery_capacity_none_renders_na(capsys):
    collector = _make_fake_collector()
    collector.get_battery_snapshot.return_value = _mk(
        status="Charging", capacity=None, power_watts=15.0,
        hours_left=None, health_percent=95.0, online=True,
    )
    _run_main_once(collector, system="Linux")

    assert "Capacity:   N/A" in capsys.readouterr().out


def test_main_battery_discharging_shows_time_remaining(capsys):
    collector = _make_fake_collector()
    collector.get_battery_snapshot.return_value = _mk(
        status="Discharging", capacity=50, power_watts=10.0,
        hours_left=3.5, health_percent=90.0, online=False,
    )
    _run_main_once(collector, system="Linux")

    assert "3h 30m remaining" in capsys.readouterr().out


def test_main_battery_wall_power(capsys):
    collector = _make_fake_collector()
    collector.get_battery_snapshot.return_value = _mk(
        status="Charging", capacity=80, power_watts=15.0,
        hours_left=None, health_percent=95.0, online=True,
    )
    _run_main_once(collector, system="Linux")

    assert "Wall Power (AC)" in capsys.readouterr().out


# ===========================================================================
# main() — thermal / GPU branches
# ===========================================================================

def test_main_thermal_unavailable(capsys):
    collector = _make_fake_collector()
    collector.get_thermal_snapshot.side_effect = RuntimeError("boom")
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "THERMAL & GPU" in out
    assert "Status:     Unavailable" in out


def test_main_thermal_sensor_unavailable(capsys):
    """sensor_available=False renders the hardcoded 'Unavailable' label.

    Was: rendered the removed `sensor_error` field (e.g. SENSORS_NOT_INSTALLED).
    The refactor deleted that dataclass field, so the view hardcodes it.
    """
    collector = _make_fake_collector()
    collector.get_thermal_snapshot.return_value = _mk(
        sensor_available=False,
        gpu_available=True, gpus=[],
    )
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "Sensor:     Unavailable" in out


def test_main_thermal_gpu_unavailable(capsys):
    """gpu_available=False renders 'Not Detected'.

    Was: rendered `gpu_error or 'Unavailable'`. The refactor deleted the
    `gpu_error` field, so the view uses a fixed 'Not Detected' label.
    """
    collector = _make_fake_collector()
    collector.get_thermal_snapshot.return_value = _mk(
        sensor_available=True, cpu_temp=50.0, cpu_temp_max=100.0,
        system_fans={},
        gpu_available=False, gpus=[],
    )
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "GPU:        Not Detected" in out


def test_main_thermal_gpu_available_but_empty_list(capsys):
    collector = _make_fake_collector()
    collector.get_thermal_snapshot.return_value = _mk(
        sensor_available=True, cpu_temp=50.0, cpu_temp_max=100.0,
        system_fans={}, gpu_available=True, gpus=[],
    )
    _run_main_once(collector, system="Linux")

    assert "GPU:        N/A" in capsys.readouterr().out


# ===========================================================================
# main() — disk space branches
# ===========================================================================

def test_main_disk_space_normal_uses_format_disk_size(capsys):
    _run_main_once(_make_fake_collector(), system="Linux")
    out = capsys.readouterr().out
    assert "500.00 GB" in out
    assert "250.00 GB" in out


def test_main_disk_space_error_shows_unavailable(capsys):
    collector = _make_fake_collector()
    collector.get_disk_space_snapshot.side_effect = RuntimeError("boom")
    _run_main_once(collector, system="Linux")

    assert "Unavailable" in capsys.readouterr().out


def test_main_disk_space_none_fields(capsys):
    """Sampler returns DiskSpaceSnapshot with total_bytes=None (read failed)."""
    collector = _make_fake_collector()
    collector.get_disk_space_snapshot.return_value = _mk(
        total_bytes=None, used_bytes=None, free_bytes=None, percent=None,
    )
    _run_main_once(collector, system="Linux")

    assert "Unavailable (read failed)" in capsys.readouterr().out


# ===========================================================================
# main() — disk I/O branches (refactored to None / [] / data triage)
# ===========================================================================

def test_main_disk_io_normal_uses_format_disk_speed(capsys):
    _run_main_once(_make_fake_collector(), system="Linux")
    out = capsys.readouterr().out
    assert "sda:" in out
    assert "1.00 MB/s" in out   # 1_048_576 bps
    assert "2.00 MB/s" in out   # 2_097_152 bps


def test_main_disk_io_initializing(capsys):
    """disk_io == [] (first tick, baseline priming) -> 'Initializing'."""
    collector = _make_fake_collector()
    collector.get_disk_io_snapshot.return_value = []
    _run_main_once(collector, system="Linux")

    assert "Initializing (1s delta)" in capsys.readouterr().out


def test_main_disk_io_unavailable_when_none(capsys):
    """disk_io is None (sampler unavailable) -> 'Unavailable'."""
    collector = _make_fake_collector()
    collector.get_disk_io_snapshot.return_value = None
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "DISK I/O" in out
    # No per-device rows rendered
    assert "sda:" not in out


# ===========================================================================
# main() — network branches (refactored to None / [] / data triage)
# ===========================================================================

def test_main_network_connected_uses_format_speed_bits(capsys):
    _run_main_once(_make_fake_collector(), system="Linux")
    out = capsys.readouterr().out
    assert "eth0 (CONNECTED)" in out
    assert "8.00 Mbps" in out   # 1_000_000 bytes/s
    assert "4.00 Mbps" in out   # 500_000 bytes/s


def test_main_network_disconnected(capsys):
    collector = _make_fake_collector()
    collector.get_network_snapshot.return_value = [
        _mk(
            interface="wlan0", status="DISCONNECTED",
            download_bps=0.0, upload_bps=0.0,
            rx_errors=0, tx_errors=0, rx_drops=0, tx_drops=0,
            total_bytes=0.0,
        ),
    ]
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "wlan0 (DISCONNECTED)" in out
    assert "Offline / Unplugged" in out


def test_main_network_connecting(capsys):
    collector = _make_fake_collector()
    collector.get_network_snapshot.return_value = [
        _mk(
            interface="wlan0", status="CONNECTING",
            download_bps=0.0, upload_bps=0.0,
            rx_errors=0, tx_errors=0, rx_drops=0, tx_drops=0,
            total_bytes=1_000_000,
        ),
    ]
    _run_main_once(collector, system="Linux")

    assert "Initializing link..." in capsys.readouterr().out


def test_main_network_initializing(capsys):
    """network_data == [] (first tick) -> 'Initializing'."""
    collector = _make_fake_collector()
    collector.get_network_snapshot.return_value = []
    _run_main_once(collector, system="Linux")

    assert "Initializing (1s delta)" in capsys.readouterr().out


def test_main_network_unavailable_when_none(capsys):
    """network_data is None (sampler unavailable) -> 'Unavailable'."""
    collector = _make_fake_collector()
    collector.get_network_snapshot.return_value = None
    _run_main_once(collector, system="Linux")

    out = capsys.readouterr().out
    assert "NETWORK" in out
    # No per-interface rows rendered
    assert "eth0 (CONNECTED)" not in out


# ===========================================================================
# main() — terminal clear command
# ===========================================================================

def test_main_calls_clear_on_linux():
    """Once for the Initializing splash, once per loop iteration."""
    collector = _make_fake_collector()
    with patch("main.platform.system", return_value="Linux"), \
         patch("main.LinuxCollector", return_value=collector), \
         patch("main.os.system") as mock_os_sys, \
         patch("main.shutil.get_terminal_size") as ts, \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        ts.return_value = os.terminal_size((200, 40))
        main()

    assert mock_os_sys.call_count == 2
    assert mock_os_sys.call_args[0][0] == "clear"


def test_main_calls_cls_on_windows():
    collector = _make_fake_collector()
    with patch("main.platform.system", return_value="Windows"), \
         patch("main.PsutilCollector", return_value=collector), \
         patch("main.os.system") as mock_os_sys, \
         patch("main.shutil.get_terminal_size") as ts, \
         patch("main.time.sleep", side_effect=KeyboardInterrupt):
        ts.return_value = os.terminal_size((200, 40))
        main()

    assert mock_os_sys.call_count == 2
    assert mock_os_sys.call_args[0][0] == "cls"