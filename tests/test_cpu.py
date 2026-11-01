from unittest.mock import patch
from engine.linux_cpu import LinuxCpuSampler


def test_cpu_sampler_normal_tick():
    sampler = LinuxCpuSampler.__new__(LinuxCpuSampler)
    sampler.stat_path = "/proc/stat"
    sampler._last_total = 100_000.0
    sampler._last_idle = 60_000.0

    with patch.object(sampler, "_get_raw_times", return_value=(101_000.0, 60_500.0)):
        snap = sampler.get_snapshot()

    # 1000 total ticks, 500 idle -> 50% usage
    assert snap.usage_pct == 50.0
    assert sampler._last_total == 101_000.0
    assert sampler._last_idle == 60_500.0


def test_cpu_sampler_does_not_corrupt_baseline_on_failed_read():
    """A failed /proc/stat read must not overwrite the last good baseline."""
    sampler = LinuxCpuSampler.__new__(LinuxCpuSampler)
    sampler.stat_path = "/proc/stat"
    sampler._last_total = 100_000.0
    sampler._last_idle = 60_000.0

    # Simulate a transient read failure: _get_raw_times returns its (0, 0) sentinel
    with patch.object(sampler, "_get_raw_times", return_value=(0.0, 0.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0
    # Baseline MUST be untouched
    assert sampler._last_total == 100_000.0
    assert sampler._last_idle == 60_000.0

    # Next good read: small delta -> sane usage %, NOT boot-average
    with patch.object(sampler, "_get_raw_times", return_value=(100_500.0, 60_400.0)):
        snap = sampler.get_snapshot()

    # 500 total ticks, 400 idle -> 20% usage
    assert snap.usage_pct == 20.0
    assert sampler._last_total == 100_500.0
    assert sampler._last_idle == 60_400.0


def test_cpu_sampler_first_read_after_failed_init():
    """When __init__ swallowed FileNotFoundError, first good read seeds only."""
    sampler = LinuxCpuSampler.__new__(LinuxCpuSampler)
    sampler.stat_path = "/proc/stat"
    sampler._last_total = 0.0
    sampler._last_idle = 0.0

    # First successful read: seed baseline, report 0% for this tick
    with patch.object(sampler, "_get_raw_times", return_value=(100_000.0, 60_000.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0
    assert sampler._last_total == 100_000.0
    assert sampler._last_idle == 60_000.0

    # Second read: now we have a real baseline -> correct delta
    with patch.object(sampler, "_get_raw_times", return_value=(100_500.0, 60_400.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 20.0


def test_cpu_sampler_delta_total_non_positive():
    """If total ticks somehow go backwards, report 0% instead of dividing."""
    sampler = LinuxCpuSampler.__new__(LinuxCpuSampler)
    sampler.stat_path = "/proc/stat"
    sampler._last_total = 100_000.0
    sampler._last_idle = 60_000.0

    # current_total < _last_total (impossible on real Linux, but defensive)
    with patch.object(sampler, "_get_raw_times", return_value=(99_000.0, 59_000.0)):
        snap = sampler.get_snapshot()

    assert snap.usage_pct == 0.0
    # Baseline updated to the new value so we recover on the next tick
    assert sampler._last_total == 99_000.0
    assert sampler._last_idle == 59_000.0