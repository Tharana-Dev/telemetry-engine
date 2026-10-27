"""Tests for the psutil-based battery collector."""

from collections import namedtuple
from unittest.mock import patch

from engine.psutil_sampler import PsutilCollector


# Mirror the shape psutil.sensors_battery() returns.
FakeSBattery = namedtuple("sbattery", ["percent", "secsleft", "power_plugged"])


def test_psutil_happy_path():
    """psutil reports a battery, plugged in at 50%."""
    fake = FakeSBattery(percent=50, secsleft=-1, power_plugged=True)

    with patch("engine.psutil_sampler.psutil.sensors_battery", return_value=fake):
        snapshot = PsutilCollector().get_battery_snapshot()

    assert snapshot is not None
    assert snapshot.capacity == 50
    assert snapshot.online is True
    assert snapshot.status == "Charging"


def test_psutil_desktop_fallback():
    """psutil returns None (desktop / no battery) -> propagate None."""
    with patch("engine.psutil_sampler.psutil.sensors_battery", return_value=None):
        snapshot = PsutilCollector().get_battery_snapshot()

    assert snapshot is None