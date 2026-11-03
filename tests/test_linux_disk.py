from unittest.mock import patch, MagicMock
from engine.linux_disk import LinuxDiskSampler
from engine.results_and_errors import Errors


def test_disk_space_snapshot():
    fake_usage = MagicMock()
    fake_usage.total = 1000 * (1024**3)
    fake_usage.used = 400 * (1024**3)
    fake_usage.free = 600 * (1024**3)
    fake_usage.percent = 40.0

    with patch("engine.linux_disk.shutil.disk_usage", return_value=fake_usage):
        snap = LinuxDiskSampler().get_space_snapshot()

    assert snap.total_gb == 1000.0
    assert snap.used_gb == 400.0
    assert snap.free_gb == 600.0
    assert snap.percent == 40.0


def test_disk_space_exception_returns_zeros():
    with patch("engine.linux_disk.shutil.disk_usage", side_effect=OSError):
        snap = LinuxDiskSampler().get_space_snapshot()

    assert snap.total_gb == 0.0
    assert snap.used_gb == 0.0
    assert snap.free_gb == 0.0
    assert snap.percent == 0.0


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
    assert snaps[0].read_mib == 1.0
    assert snaps[0].write_mib == 2.0


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

    assert snaps[0].read_mib == 0.0
    assert snaps[0].write_mib == 0.0


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

    assert snaps[0].read_mib == 1.0
    assert snaps[0].write_mib == 1.0


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