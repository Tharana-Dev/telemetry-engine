from unittest.mock import patch

import pytest

from engine.linux_cpu import LinuxCpuSampler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bare_sampler(last_total: float, last_idle: float) -> LinuxCpuSampler:
    """Construct a sampler without touching /proc/stat."""
    s = LinuxCpuSampler.__new__(LinuxCpuSampler)
    s.stat_path = "/proc/stat"
    s._last_total = last_total
    s._last_idle = last_idle
    return s


def _write_stat(tmp_path, content: str) -> str:
    p = tmp_path / "stat"
    p.write_text(content, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Existing tests (kept)
# ---------------------------------------------------------------------------

def test_cpu_sampler_normal_tick():
    sampler = _bare_sampler(100_000.0, 60_000.0)
    with patch.object(sampler, "_get_raw_times", return_value=(101_000.0, 60_500.0)):
        snap = sampler.get_snapshot()

    # 1000 total ticks, 500 idle -> 50% usage
    assert snap.usage_pct == 50.0
    assert sampler._last_total == 101_000.0
    assert sampler._last_idle == 60_500.0


def test_cpu_sampler_does_not_corrupt_baseline_on_failed_read():
    """A failed /proc/stat read must not overwrite the last good baseline."""
    sampler = _bare_sampler(100_000.0, 60_000.0)

    with patch.object(sampler, "_get_raw_times", return_value=(0.0, 0.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0
    assert sampler._last_total == 100_000.0
    assert sampler._last_idle == 60_000.0

    with patch.object(sampler, "_get_raw_times", return_value=(100_500.0, 60_400.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 20.0
    assert sampler._last_total == 100_500.0
    assert sampler._last_idle == 60_400.0


def test_cpu_sampler_first_read_after_failed_init():
    """When __init__ swallowed FileNotFoundError, first good read seeds only."""
    sampler = _bare_sampler(0.0, 0.0)

    with patch.object(sampler, "_get_raw_times", return_value=(100_000.0, 60_000.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0
    assert sampler._last_total == 100_000.0
    assert sampler._last_idle == 60_000.0

    with patch.object(sampler, "_get_raw_times", return_value=(100_500.0, 60_400.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 20.0


def test_cpu_sampler_delta_total_non_positive():
    """If total ticks go backwards, report 0% instead of dividing."""
    sampler = _bare_sampler(100_000.0, 60_000.0)

    with patch.object(sampler, "_get_raw_times", return_value=(99_000.0, 59_000.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0
    # Baseline updated so we recover on the next tick
    assert sampler._last_total == 99_000.0
    assert sampler._last_idle == 59_000.0


def test_cpu_sampler_delta_total_zero():
    """Exactly zero total delta (file replaced, same values) -> 0%, no div-by-0."""
    sampler = _bare_sampler(100_000.0, 60_000.0)

    with patch.object(sampler, "_get_raw_times", return_value=(100_000.0, 60_000.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0
    assert sampler._last_total == 100_000.0


# ---------------------------------------------------------------------------
# C1: clamp to [0, 100]
# ---------------------------------------------------------------------------

def test_cpu_sampler_iowait_regression_clamped_to_100():
    """C1: iowait going *down* makes delta_idle negative -> usage > 100%.

    Naive formula gives 1 - (-50/100) = 150%. Must be clamped to 100.
    """
    sampler = _bare_sampler(100_000.0, 60_000.0)

    # delta_total = +100, delta_idle = -50
    with patch.object(sampler, "_get_raw_times", return_value=(100_100.0, 59_950.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 100.0


def test_cpu_sampler_delta_idle_exceeds_total_clamped_to_0():
    """C1: delta_idle > delta_total -> negative usage. Must clamp to 0.

    Can happen when iowait drops hard while idle ticks up, so the combined
    idle bucket outgrows the total. Naive formula gives 1 - 200/100 = -100%.
    """
    sampler = _bare_sampler(100_000.0, 60_000.0)

    # delta_total = +100, delta_idle = +200
    with patch.object(sampler, "_get_raw_times", return_value=(100_100.0, 60_200.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0


def test_cpu_sampler_exact_zero_usage():
    """All ticks idle -> 0%."""
    sampler = _bare_sampler(100_000.0, 60_000.0)
    with patch.object(sampler, "_get_raw_times", return_value=(101_000.0, 61_000.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0


def test_cpu_sampler_exact_hundred_usage():
    """No idle ticks -> 100%."""
    sampler = _bare_sampler(100_000.0, 60_000.0)
    with patch.object(sampler, "_get_raw_times", return_value=(101_000.0, 60_000.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 100.0


def test_cpu_sampler_clamp_does_not_pollute_baseline():
    """C1 clamp only affects the reported value; baseline still advances."""
    sampler = _bare_sampler(100_000.0, 60_000.0)

    with patch.object(sampler, "_get_raw_times", return_value=(100_100.0, 59_950.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 100.0
    assert sampler._last_total == 100_100.0
    assert sampler._last_idle == 59_950.0

    # A subsequent normal tick must recover a sane number, not stay stuck at 100.
    with patch.object(sampler, "_get_raw_times", return_value=(101_100.0, 60_450.0)):
        snap = sampler.get_snapshot()

    # delta_total = 1000, delta_idle = 500 -> 50%
    assert snap.usage_pct == 50.0


# ---------------------------------------------------------------------------
# Rounding edges
# ---------------------------------------------------------------------------

def test_cpu_sampler_rounds_to_two_decimals():
    """66.666...% -> 66.67."""
    sampler = _bare_sampler(100_000.0, 60_000.0)
    with patch.object(sampler, "_get_raw_times", return_value=(100_003.0, 60_001.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 66.67


def test_cpu_sampler_rounds_99_999_up_to_100():
    """1 idle tick in 100k -> 99.999% -> round(., 2) == 100.0."""
    sampler = _bare_sampler(100_000.0, 60_000.0)
    with patch.object(sampler, "_get_raw_times", return_value=(200_000.0, 60_001.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 100.0


def test_cpu_sampler_rounds_0_001_down_to_zero():
    """1 - 999_990/1_000_000 = 0.00001 -> 0.001% -> round(., 2) == 0.0."""
    sampler = _bare_sampler(100_000.0, 60_000.0)
    with patch.object(sampler, "_get_raw_times", return_value=(1_100_000.0, 1_059_990.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0


# ---------------------------------------------------------------------------
# _get_raw_times: real parser, exercised via tmp files
# ---------------------------------------------------------------------------

def test_get_raw_times_parses_aggregate_line(tmp_path):
    """Real /proc/stat line: total = sum(first 8), idle = fields 4 + 5 (1-based)."""
    path = _write_stat(
        tmp_path,
        # cpu   user nice system idle iowait irq softirq steal guest guest_nice
        "cpu    100  50   200   3000 500    10  20      0     0     0\n"
        "cpu0   50   25   100   1500 250    5   10      0     0     0\n",
    )
    s = LinuxCpuSampler(stat_path=path)
    total, idle = s._get_raw_times()

    assert total == 100 + 50 + 200 + 3000 + 500 + 10 + 20 + 0
    assert idle == 3000 + 500


def test_get_raw_times_ignores_per_cpu_lines(tmp_path):
    """Only the first (aggregate) line is read; cpu0/cpu1 must not leak in."""
    path = _write_stat(
        tmp_path,
        "cpu   10 10 10 10 10 10 10 10\n"
        "cpu0  999 999 999 999 999 999 999 999\n",
    )
    total, idle = LinuxCpuSampler(stat_path=path)._get_raw_times()

    assert total == 80
    assert idle == 20


def test_get_raw_times_minimum_five_fields(tmp_path):
    """Pre-2.6 kernels expose only user/nice/system/idle/iowait — still valid."""
    path = _write_stat(tmp_path, "cpu 100 50 200 3000 500\n")
    total, idle = LinuxCpuSampler(stat_path=path)._get_raw_times()

    assert total == 3850
    assert idle == 3500


def test_get_raw_times_too_few_fields_returns_zero(tmp_path):
    """Fewer than 5 numeric fields -> (0, 0) sentinel."""
    path = _write_stat(tmp_path, "cpu 100 50 200 3000\n")
    assert LinuxCpuSampler(stat_path=path)._get_raw_times() == (0.0, 0.0)


def test_get_raw_times_malformed_number_returns_zero(tmp_path):
    """Non-numeric token anywhere -> (0, 0); does not raise."""
    path = _write_stat(tmp_path, "cpu 100 abc 200 3000 500\n")
    assert LinuxCpuSampler(stat_path=path)._get_raw_times() == (0.0, 0.0)


def test_get_raw_times_empty_file_returns_zero(tmp_path):
    """Empty file -> readline() returns '' -> (0, 0)."""
    path = _write_stat(tmp_path, "")
    assert LinuxCpuSampler(stat_path=path)._get_raw_times() == (0.0, 0.0)


def test_get_raw_times_whitespace_only_line_returns_zero(tmp_path):
    """'  \\n' -> split() gives [] -> < 5 fields -> (0, 0)."""
    path = _write_stat(tmp_path, "   \n")
    assert LinuxCpuSampler(stat_path=path)._get_raw_times() == (0.0, 0.0)


def test_get_raw_times_missing_file_returns_zero(tmp_path):
    """Deleted / unreadable file -> IOError swallowed -> (0, 0)."""
    assert LinuxCpuSampler(
        stat_path=str(tmp_path / "nope")
    )._get_raw_times() == (0.0, 0.0)


# ---------------------------------------------------------------------------
# __init__ / _initialize_first_tick
# ---------------------------------------------------------------------------

def test_init_missing_file_does_not_raise(tmp_path):
    """__init__ swallows FileNotFoundError; baseline stays 0."""
    s = LinuxCpuSampler(stat_path=str(tmp_path / "missing"))
    assert s._last_total == 0.0
    assert s._last_idle == 0.0


def test_init_empty_file_does_not_raise(tmp_path):
    """_initialize_first_tick raises on empty file; __init__ catches it."""
    path = _write_stat(tmp_path, "")
    s = LinuxCpuSampler(stat_path=path)
    assert s._last_total == 0.0
    assert s._last_idle == 0.0


def test_init_valid_file_seeds_baseline(tmp_path):
    """Constructor seeds the first tick so the first get_snapshot() is a delta."""
    path = _write_stat(tmp_path, "cpu 100 50 200 3000 500 10 20 0\n")
    s = LinuxCpuSampler(stat_path=path)

    assert s._last_total == 100 + 50 + 200 + 3000 + 500 + 10 + 20 + 0
    assert s._last_idle == 3000 + 500


def test_init_then_first_snapshot_is_zero(tmp_path):
    """After a successful __init__, the very first snapshot has no prior tick."""
    path = _write_stat(tmp_path, "cpu 100 50 200 3000 500 10 20 0\n")
    s = LinuxCpuSampler(stat_path=path)

    assert s.get_snapshot().usage_pct == 0.0