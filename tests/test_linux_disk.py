from unittest.mock import patch, MagicMock

import pytest

from engine.linux_disk import LinuxDiskSampler


# ===========================================================================
# DISK SPACE
# ===========================================================================

def test_disk_space_snapshot_returns_raw_bytes():
    fake_usage = MagicMock()
    fake_usage.total = 1000 * (1024 ** 3)   # int, no division in sampler
    fake_usage.used = 400 * (1024 ** 3)
    fake_usage.free = 600 * (1024 ** 3)

    with patch("engine.linux_disk.shutil.disk_usage", return_value=fake_usage):
        snap = LinuxDiskSampler().get_space_snapshot()

    # Sampler returns raw bytes — view formats. No /1024**3 here.
    assert snap.total_bytes == 1000 * 1024 ** 3
    assert snap.used_bytes == 400 * 1024 ** 3
    assert snap.free_bytes == 600 * 1024 ** 3
    assert snap.percent == 40.0


def test_disk_space_percent_rounds_to_one_decimal():
    fake_usage = MagicMock()
    fake_usage.total = 3_000
    fake_usage.used = 1_000   # 33.333…%
    fake_usage.free = 2_000

    with patch("engine.linux_disk.shutil.disk_usage", return_value=fake_usage):
        snap = LinuxDiskSampler().get_space_snapshot()

    assert snap.percent == 33.3


def test_disk_space_zero_total_percent_is_none():
    """Guard against div-by-zero when total is 0 (partial: percent is None,
    byte counts still populated)."""
    fake_usage = MagicMock()
    fake_usage.total = 0
    fake_usage.used = 0
    fake_usage.free = 0

    with patch("engine.linux_disk.shutil.disk_usage", return_value=fake_usage):
        snap = LinuxDiskSampler().get_space_snapshot()

    assert snap.total_bytes == 0
    assert snap.percent is None


def test_disk_space_oserror_raises():
    """Fatal: disk_usage failures now bubble (was: all-None snapshot).

    The sampler no longer catches; the caller is expected to handle.
    """
    with patch("engine.linux_disk.shutil.disk_usage", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            LinuxDiskSampler().get_space_snapshot()


def test_disk_space_permission_error_raises():
    """Fatal: PermissionError from disk_usage bubbles to the caller."""
    with patch("engine.linux_disk.shutil.disk_usage",
               side_effect=PermissionError(13, "Permission denied")):
        with pytest.raises(PermissionError):
            LinuxDiskSampler().get_space_snapshot()


# ===========================================================================
# DISK I/O
# ===========================================================================

def test_disk_io_first_run_primes_baseline(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text("8 0 sda 100 0 2000 0 100 0 4000 0 0 0 0\n")

    sampler = LinuxDiskSampler(diskstats_path=str(f))

    assert sampler.get_io_snapshot() == []
    assert sampler._last_stats is not None


@patch("engine.linux_disk.time.monotonic")
def test_disk_io_delta_math(mock_time, tmp_path):
    f = tmp_path / "diskstats"
    f.write_text("8 0 sda 100 0 2048 0 100 0 4096 0 0 0 0\n")
    mock_time.return_value = 100.0
    sampler = LinuxDiskSampler(diskstats_path=str(f))
    sampler.get_io_snapshot()

    f.write_text("8 0 sda 200 0 4096 0 200 0 8192 0 0 0 0\n")
    mock_time.return_value = 101.0
    snaps = sampler.get_io_snapshot()

    assert len(snaps) == 1
    # Raw bytes/sec: 2048 sectors * 512 = 1 MiB/s; 4096 * 512 = 2 MiB/s
    assert snaps[0].read_bps == 1024 * 1024
    assert snaps[0].write_bps == 2 * 1024 * 1024


@patch("engine.linux_disk.time.monotonic")
def test_disk_io_negative_delta_clamped(mock_time, tmp_path):
    f = tmp_path / "diskstats"
    f.write_text("8 0 sda 100 0 10000 0 100 0 10000 0 0 0 0\n")
    mock_time.return_value = 100.0
    sampler = LinuxDiskSampler(diskstats_path=str(f))
    sampler.get_io_snapshot()

    f.write_text("8 0 sda 100 0 5000 0 100 0 5000 0 0 0 0\n")
    mock_time.return_value = 101.0
    snaps = sampler.get_io_snapshot()

    assert snaps[0].read_bps == 0
    assert snaps[0].write_bps == 0


@patch("engine.linux_disk.time.monotonic")
def test_disk_io_zero_duration_treated_as_one_second(mock_time, tmp_path):
    f = tmp_path / "diskstats"
    f.write_text("8 0 sda 100 0 0 0 100 0 0 0 0 0 0\n")
    mock_time.return_value = 100.0
    sampler = LinuxDiskSampler(diskstats_path=str(f))
    sampler.get_io_snapshot()

    f.write_text("8 0 sda 100 0 2048 0 100 0 2048 0 0 0 0\n")
    mock_time.return_value = 100.0
    snaps = sampler.get_io_snapshot()

    # Duration clamped to 1.0s → 2048 sectors * 512 = 1 MiB/s
    assert snaps[0].read_bps == 1024 * 1024
    assert snaps[0].write_bps == 1024 * 1024


@patch("engine.linux_disk.time.monotonic")
def test_disk_io_new_device_not_in_output(mock_time, tmp_path):
    f = tmp_path / "diskstats"
    f.write_text("8 0 sda 100 0 0 0 100 0 0 0 0 0 0\n")
    mock_time.return_value = 100.0
    sampler = LinuxDiskSampler(diskstats_path=str(f))
    sampler.get_io_snapshot()

    f.write_text(
        "8 0 sda 100 0 2048 0 100 0 2048 0 0 0 0\n"
        "259 0 nvme0n1 100 0 999 0 100 0 999 0 0 0 0\n"
    )
    mock_time.return_value = 101.0
    snaps = sampler.get_io_snapshot()

    assert [s.device for s in snaps] == ["sda"]


# ===========================================================================
# DISK STATS PARSING
# ===========================================================================

def test_disk_io_filters_partitions_and_virtual(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text(
        "8 0 sda 100 0 100 0 100 0 100 0 0 0 0\n"
        "8 1 sda1 100 0 100 0 100 0 100 0 0 0 0\n"
        "7 0 loop0 100 0 100 0 100 0 100 0 0 0 0\n"
    )

    stats = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert set(stats) == {"sda"}


def test_disk_stats_accepts_nvme_and_mmc(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text(
        "259 0 nvme0n1 0 0 0 0 0 0 0 0 0 0 0\n"
        "179 0 mmcblk0 0 0 0 0 0 0 0 0 0 0 0\n"
        "8 0 hda 0 0 0 0 0 0 0 0 0 0 0\n"
        "252 0 vda 0 0 0 0 0 0 0 0 0 0 0\n"
    )

    stats = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert set(stats) == {"nvme0n1", "mmcblk0", "hda", "vda"}


def test_disk_stats_no_valid_devices_returns_empty_dict(tmp_path):
    """No matching devices -> empty dict (was: Errors.NOT_PRESENT).

    Empty dict is the "no hardware" signal; get_io_snapshot turns it into [].
    """
    f = tmp_path / "diskstats"
    f.write_text(
        "8 1 sda1 100 0 100 0 100 0 100 0 0 0 0\n"
        "7 0 loop0 100 0 100 0 100 0 100 0 0 0 0\n"
    )

    stats = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert stats == {}


def test_disk_stats_missing_file_raises(tmp_path):
    """Fatal: missing /proc/diskstats now bubbles FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        LinuxDiskSampler(
            diskstats_path=str(tmp_path / "nope")
        )._get_disk_stats()


def test_disk_stats_malformed_field_skips_device(tmp_path):
    """Partial: non-numeric field on one device -> skip that device, no raise.

    Was: Errors.PARSE_FAILED (whole-file failure). Now per-line try/except
    continues, so the result is whatever other valid lines produced.
    """
    f = tmp_path / "diskstats"
    f.write_text("8 0 sda 100 0 abc 0 100 0 4000 0 0 0 0\n")

    stats = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert stats == {}


def test_disk_stats_malformed_field_does_not_poison_other_devices(tmp_path):
    """Partial: one bad device does not drop the good ones."""
    f = tmp_path / "diskstats"
    f.write_text(
        "8 0 sda 100 0 abc 0 100 0 4000 0 0 0 0\n"
        "8 16 sdb 100 0 200 0 100 0 400 0 0 0 0\n"
    )

    stats = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert set(stats) == {"sdb"}


def test_disk_stats_short_lines_skipped(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text(
        "8 0 sda 100 0\n"
        "8 0 sda 100 0 100 0 100 0 100 0 0 0 0\n"
    )

    stats = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert set(stats) == {"sda"}


def test_get_io_snapshot_missing_file_raises(tmp_path):
    """Fatal: missing file bubbles from get_io_snapshot (was: return []).

    Baseline is not touched because the exception short-circuits before any
    assignment in get_io_snapshot().
    """
    sampler = LinuxDiskSampler(diskstats_path=str(tmp_path / "nope"))

    with pytest.raises(FileNotFoundError):
        sampler.get_io_snapshot()

    assert sampler._last_stats is None


# ===========================================================================
# STATE (rewritten — public state properties were removed)
# ===========================================================================

def test_empty_tick_still_primes_baseline(tmp_path):
    """First tick with an empty file seeds _last_stats = {}.

    was_known_devices / is_primed properties are gone; the observable
    equivalent is inspecting _last_stats directly.
    """
    f = tmp_path / "diskstats"
    f.write_text("")
    sampler = LinuxDiskSampler(diskstats_path=str(f))

    assert sampler.get_io_snapshot() == []
    assert sampler._last_stats == {}
    assert sampler._last_time is not None


def test_broken_file_leaves_baseline_unset(tmp_path):
    """Fatal on first tick: _last_stats stays None (exception prevents seeding)."""
    sampler = LinuxDiskSampler(diskstats_path=str(tmp_path / "nope"))

    with pytest.raises(FileNotFoundError):
        sampler.get_io_snapshot()

    assert sampler._last_stats is None
    assert sampler._last_time is None