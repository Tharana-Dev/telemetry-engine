from unittest.mock import patch, MagicMock
from engine.linux_disk import LinuxDiskSampler
from engine.results_and_errors import Errors


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
    """Guard against div-by-zero when total is 0."""
    fake_usage = MagicMock()
    fake_usage.total = 0
    fake_usage.used = 0
    fake_usage.free = 0

    with patch("engine.linux_disk.shutil.disk_usage", return_value=fake_usage):
        snap = LinuxDiskSampler().get_space_snapshot()

    assert snap.total_bytes == 0
    assert snap.percent is None


def test_disk_space_exception_returns_none_snapshot():
    """Read failure is not a crash — None signals 'no data' to the view."""
    with patch("engine.linux_disk.shutil.disk_usage", side_effect=OSError):
        snap = LinuxDiskSampler().get_space_snapshot()

    assert snap.total_bytes is None
    assert snap.used_bytes is None
    assert snap.free_bytes is None
    assert snap.percent is None


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
# DISK STATS PARSING (unchanged)
# ===========================================================================

def test_disk_io_filters_partitions_and_virtual(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text(
        "8 0 sda 100 0 100 0 100 0 100 0 0 0 0\n"
        "8 1 sda1 100 0 100 0 100 0 100 0 0 0 0\n"
        "7 0 loop0 100 0 100 0 100 0 100 0 0 0 0\n"
    )

    result = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert result.error is None
    assert set(result.data) == {"sda"}


def test_disk_stats_accepts_nvme_and_mmc(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text(
        "259 0 nvme0n1 0 0 0 0 0 0 0 0 0 0 0\n"
        "179 0 mmcblk0 0 0 0 0 0 0 0 0 0 0 0\n"
        "8 0 hda 0 0 0 0 0 0 0 0 0 0 0\n"
        "252 0 vda 0 0 0 0 0 0 0 0 0 0 0\n"
    )

    result = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert result.error is None
    assert set(result.data) == {"nvme0n1", "mmcblk0", "hda", "vda"}


def test_disk_stats_no_valid_devices_is_not_present(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text(
        "8 1 sda1 100 0 100 0 100 0 100 0 0 0 0\n"
        "7 0 loop0 100 0 100 0 100 0 100 0 0 0 0\n"
    )

    result = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert result.data is None
    assert result.error == Errors.NOT_PRESENT


def test_disk_stats_missing_file_is_file_not_found(tmp_path):
    result = LinuxDiskSampler(
        diskstats_path=str(tmp_path / "nope")
    )._get_disk_stats()

    assert result.data is None
    assert result.error == Errors.FILE_NOT_FOUND


def test_disk_stats_non_numeric_is_parse_failed(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text("8 0 sda 100 0 abc 0 100 0 4000 0 0 0 0\n")

    result = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert result.data is None
    assert result.error == Errors.PARSE_FAILED


def test_disk_stats_short_lines_skipped(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text(
        "8 0 sda 100 0\n"
        "8 0 sda 100 0 100 0 100 0 100 0 0 0 0\n"
    )

    result = LinuxDiskSampler(diskstats_path=str(f))._get_disk_stats()

    assert result.error is None
    assert set(result.data) == {"sda"}


def test_get_io_snapshot_returns_empty_on_error(tmp_path):
    sampler = LinuxDiskSampler(diskstats_path=str(tmp_path / "nope"))

    assert sampler.get_io_snapshot() == []
    assert sampler._last_stats is None


# ===========================================================================
# STATE PROPERTIES (unchanged)
# ===========================================================================

def test_state_after_first_tick_with_devices(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text("8 0 sda 0 0 0 0 0 0 0 0 0 0 0\n")
    sampler = LinuxDiskSampler(diskstats_path=str(f))
    sampler.get_io_snapshot()
    assert sampler.is_primed
    assert sampler.has_known_devices
    assert sampler.last_error is None


def test_state_no_devices_after_tick(tmp_path):
    f = tmp_path / "diskstats"
    f.write_text("")  # file exists, no lines
    sampler = LinuxDiskSampler(diskstats_path=str(f))
    assert sampler.get_io_snapshot() == []
    assert sampler.is_primed          # we ticked
    assert not sampler.has_known_devices  # no devices ever
    assert sampler.last_error is None


def test_state_broken_file(tmp_path):
    sampler = LinuxDiskSampler(diskstats_path=str(tmp_path / "nope"))
    assert sampler.get_io_snapshot() == []
    assert sampler.last_error == Errors.FILE_NOT_FOUND
    assert not sampler.is_primed      # never ticked successfully