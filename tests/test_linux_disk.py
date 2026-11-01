import pytest
from unittest.mock import patch, MagicMock
from engine.linux_disk import LinuxDisk
from engine.models import DiskIOSnapshot, DiskSpaceSnapshot

def test_disk_space_snapshot():
    # Mock the psutil response so we don't depend on the actual machine's disk
    fake_usage = MagicMock()
    fake_usage.total = 1000 * (1024**3)  # 1000 GB
    fake_usage.used = 400 * (1024**3)    # 400 GB
    fake_usage.free = 600 * (1024**3)    # 600 GB
    fake_usage.percent = 40.0

    with patch("engine.linux_disk.psutil.disk_usage", return_value=fake_usage):
        sampler = LinuxDisk()
        snapshot = sampler.get_space_snapshot()

        assert snapshot.total_gb == 1000.0
        assert snapshot.used_gb == 400.0
        assert snapshot.free_gb == 600.0
        assert snapshot.percent == 40.0


def test_disk_io_first_run_primes_baseline(tmp_path):
    fake_diskstats = tmp_path / "diskstats"
    # 8 = major, 0 = minor, sda = name, then 11 numbers (we need at least 14 fields total)
    fake_diskstats.write_text("8 0 sda 100 0 2000 0 100 0 4000 0 0 0 0\n")

    sampler = LinuxDisk(diskstats_path=str(fake_diskstats))
    snapshots = sampler.get_io_snapshot()

    # First run should return empty list because there is no delta yet
    assert snapshots == []
    assert sampler._last_stats is not None


@patch("engine.linux_disk.time.time")
def test_disk_io_delta_math(mock_time, tmp_path):
    fake_diskstats = tmp_path / "diskstats"
    
    # Baseline at Time = 100.0
    fake_diskstats.write_text("8 0 sda 100 0 2048 0 100 0 4096 0 0 0 0\n")
    mock_time.return_value = 100.0
    sampler = LinuxDisk(diskstats_path=str(fake_diskstats))
    sampler.get_io_snapshot() # Primes baseline

    # Time = 101.0 (1 second later)
    # Read delta: 4096 - 2048 = 2048 sectors
    # Write delta: 8192 - 4096 = 4096 sectors
    fake_diskstats.write_text("8 0 sda 200 0 4096 0 200 0 8192 0 0 0 0\n")
    mock_time.return_value = 101.0
    snapshots = sampler.get_io_snapshot()

    assert len(snapshots) == 1
    sda = snapshots[0]
    
    # Math: (2048 * 512) / (1024 * 1024) / 1.0 = 1.0 MB/s
    assert sda.read_mbps == 1.0
    # Math: (4096 * 512) / (1024 * 1024) / 1.0 = 2.0 MB/s
    assert sda.write_mbps == 2.0


def test_disk_io_filters_partitions_and_virtual(tmp_path):
    fake_diskstats = tmp_path / "diskstats"
    # sda1 is a partition, loop0 is virtual, sda is physical
    fake_diskstats.write_text(
        "8 0 sda 100 0 100 0 100 0 100 0 0 0 0\n"
        "8 1 sda1 100 0 100 0 100 0 100 0 0 0 0\n"
        "7 0 loop0 100 0 100 0 100 0 100 0 0 0 0\n"
    )

    sampler = LinuxDisk(diskstats_path=str(fake_diskstats))
    result = sampler._get_disk_stats()

    assert result.error is None
    assert "sda" in result.data
    assert "sda1" not in result.data
    assert "loop0" not in result.data