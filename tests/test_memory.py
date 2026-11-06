import os
import pytest

from engine.linux_memory import LinuxMemorySampler
from engine.models import MemorySnapshot


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mock_meminfo.txt")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_meminfo(tmp_path, content: str) -> str:
    """Write *content* to a temp meminfo file and return its path."""
    p = tmp_path / "meminfo"
    p.write_text(content, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Happy path (unchanged)
# ---------------------------------------------------------------------------

def test_memory_sampler_happy_path_and_parsing():
    sampler = LinuxMemorySampler(mem_path=FIXTURE_PATH)
    snapshot = sampler.get_snapshot()

    assert isinstance(snapshot, MemorySnapshot)
    assert snapshot.total_gb == 16.0
    assert snapshot.available_gb == 8.0
    assert snapshot.used_gb == 8.0
    assert snapshot.used_pct == 50.0

    raw_data = sampler.get_mem_data()
    assert "MemTotal" in raw_data
    assert "SpacedKey" in raw_data
    assert raw_data["SpacedKey"] == 1000


# ---------------------------------------------------------------------------
# Refactored contract: missing inputs -> None fields, not zero sentinels
# ---------------------------------------------------------------------------

def test_memory_sampler_empty_file_returns_all_none(tmp_path):
    """Empty meminfo -> no keys -> all fields None (was: all-zeros snapshot).

    The sampler no longer substitutes 0 for "no data"; missing inputs stay
    None so the view can render N/A rather than lie about 0% usage.
    """
    sampler = LinuxMemorySampler(mem_path=_write_meminfo(tmp_path, ""))
    snapshot = sampler.get_snapshot()

    assert snapshot.total_gb is None
    assert snapshot.available_gb is None
    assert snapshot.used_gb is None
    assert snapshot.used_pct is None


def test_memory_sampler_zero_total_memory_returns_partial_snapshot(tmp_path):
    """MemTotal: 0 -> total_gb=0.0 honestly, but used/pct are None.

    used = total - available is meaningless when total == 0, so those fields
    are None rather than a misleading 0.0. Byte counts that ARE known (total
    and available) are still reported.
    """
    path = _write_meminfo(tmp_path, "MemTotal: 0 kB\nMemAvailable: 0 kB\n")
    snapshot = LinuxMemorySampler(mem_path=path).get_snapshot()

    assert snapshot.total_gb == 0.0
    assert snapshot.available_gb == 0.0
    assert snapshot.used_gb is None
    assert snapshot.used_pct is None


def test_memory_sampler_missing_total_returns_partial_snapshot(tmp_path):
    """MemAvailable present but MemTotal absent -> total unknown, avail known.

    New partial state introduced by the refactor: we can report the absolute
    available figure, but without a denominator we can't compute usage %.
    """
    path = _write_meminfo(
        tmp_path,
        "MemAvailable:    8388608 kB\n",   # 8 GiB, no MemTotal line
    )
    snapshot = LinuxMemorySampler(mem_path=path).get_snapshot()

    assert snapshot.total_gb is None
    assert snapshot.available_gb == 8.0
    assert snapshot.used_gb is None
    assert snapshot.used_pct is None


def test_memory_sampler_no_available_sources_returns_partial_snapshot(tmp_path):
    """MemTotal present, no MemAvailable / MemFree / Buffers / Cached.

    Old behavior: fallback summed three missing keys as 0+0+0 = 0, then
    reported used_pct = 100% — a lie. New behavior: available is None.
    """
    path = _write_meminfo(
        tmp_path,
        "MemTotal:       16777216 kB\n",
    )
    snapshot = LinuxMemorySampler(mem_path=path).get_snapshot()

    assert snapshot.total_gb == 16.0
    assert snapshot.available_gb is None
    assert snapshot.used_gb is None
    assert snapshot.used_pct is None


# ---------------------------------------------------------------------------
# M1: MemAvailable missing -> fallback to MemFree + Buffers + Cached
# ---------------------------------------------------------------------------

def test_memory_sampler_missing_memavailable_uses_fallback(tmp_path):
    """M1: no MemAvailable line -> derive from MemFree + Buffers + Cached."""
    path = _write_meminfo(
        tmp_path,
        "MemTotal:       16777216 kB\n"   # 16 GiB
        "MemFree:         4194304 kB\n"   # 4 GiB
        "Buffers:         1048576 kB\n"   # 1 GiB
        "Cached:          3145728 kB\n",  # 3 GiB
        # fallback available = 4 + 1 + 3 = 8 GiB -> 50% used
    )
    snapshot = LinuxMemorySampler(mem_path=path).get_snapshot()

    assert snapshot.total_gb == 16.0
    assert snapshot.available_gb == 8.0
    assert snapshot.used_gb == 8.0
    assert snapshot.used_pct == 50.0


def test_memory_sampler_fallback_with_only_memfree(tmp_path):
    """M1 fallback: only MemFree present -> sum the components that exist."""
    path = _write_meminfo(
        tmp_path,
        "MemTotal:       16777216 kB\n"
        "MemFree:         8388608 kB\n",
    )
    snapshot = LinuxMemorySampler(mem_path=path).get_snapshot()

    assert snapshot.available_gb == 8.0
    assert snapshot.used_pct == 50.0


def test_memory_sampler_memavailable_zero_is_preserved(tmp_path):
    """M1: an explicit 'MemAvailable: 0' must NOT trigger the fallback.

    The fallback exists only when the key is *absent*. A present-but-zero
    reading is a real 'no memory available' signal (100% used) and must be
    preserved, not silently replaced with the fallback estimate.
    """
    path = _write_meminfo(
        tmp_path,
        "MemTotal:       16777216 kB\n"
        "MemFree:         4194304 kB\n"
        "Buffers:         1048576 kB\n"
        "Cached:          3145728 kB\n"
        "MemAvailable:          0 kB\n",
    )
    snapshot = LinuxMemorySampler(mem_path=path).get_snapshot()

    assert snapshot.available_gb == 0.0
    assert snapshot.used_gb == 16.0
    assert snapshot.used_pct == 100.0


# ---------------------------------------------------------------------------
# M2: one malformed line must not poison the whole parse
# ---------------------------------------------------------------------------

def test_memory_sampler_malformed_line_skipped_others_survive(tmp_path):
    """M2: bad integer on one line -> skip it, keep everything else.

    Crucially, dropping MemAvailable must push the snapshot through the
    fallback path rather than collapsing the whole dict to {}.
    """
    path = _write_meminfo(
        tmp_path,
        "MemTotal:       16777216 kB\n"
        "MemAvailable:   not_a_number kB\n"   # malformed
        "MemFree:         4194304 kB\n"
        "Buffers:         1048576 kB\n"
        "Cached:          3145728 kB\n",
    )
    sampler = LinuxMemorySampler(mem_path=path)

    raw = sampler.get_mem_data()
    assert raw["MemTotal"] == 16777216
    assert raw["MemFree"] == 4194304
    assert "MemAvailable" not in raw   # bad line dropped, not fatal

    snapshot = sampler.get_snapshot()
    assert snapshot.total_gb == 16.0
    assert snapshot.available_gb == 8.0          # via fallback
    assert snapshot.used_pct == 50.0


def test_memory_sampler_line_without_colon_skipped(tmp_path):
    """M2: lines with no ':' (headers, noise) are ignored, not fatal."""
    path = _write_meminfo(
        tmp_path,
        "this line has no colon\n"
        "MemTotal:       16777216 kB\n"
        "MemAvailable:    8388608 kB\n"
        "another noise line\n",
    )
    raw = LinuxMemorySampler(mem_path=path).get_mem_data()

    assert raw == {"MemTotal": 16777216, "MemAvailable": 8388608}


def test_memory_sampler_blank_and_whitespace_lines_skipped(tmp_path):
    """Empty / whitespace-only lines are harmless."""
    path = _write_meminfo(
        tmp_path,
        "\n"
        "   \n"
        "MemTotal:       16777216 kB\n"
        "\n"
        "MemAvailable:    8388608 kB\n"
        "   \n",
    )
    raw = LinuxMemorySampler(mem_path=path).get_mem_data()

    assert raw == {"MemTotal": 16777216, "MemAvailable": 8388608}


def test_memory_sampler_key_with_no_value_skipped(tmp_path):
    """'Key:' with no value tokens after the colon is skipped."""
    path = _write_meminfo(
        tmp_path,
        "MemTotal:       16777216 kB\n"
        "MemAvailable:\n"                # no value at all
        "MemFree:         4194304 kB\n",
    )
    raw = LinuxMemorySampler(mem_path=path).get_mem_data()

    assert raw["MemTotal"] == 16777216
    assert raw["MemFree"] == 4194304
    assert "MemAvailable" not in raw


# ---------------------------------------------------------------------------
# Additional edges
# ---------------------------------------------------------------------------

def test_memory_sampler_value_with_trailing_units(tmp_path):
    """Only the first whitespace-delimited token is parsed; 'kB' is ignored."""
    path = _write_meminfo(
        tmp_path,
        "MemTotal:       16777216 kB\n"
        "MemAvailable:    8388608 kB\n",
    )
    raw = LinuxMemorySampler(mem_path=path).get_mem_data()

    assert raw["MemTotal"] == 16777216
    assert raw["MemAvailable"] == 8388608


def test_memory_sampler_available_exceeds_total_documents_behavior(tmp_path):
    """Pin the current contract when available > total (buggy driver / container).

    Today this produces a negative used_gb / used_pct. If we later decide to
    clamp, this test is where the decision is made explicit.
    """
    path = _write_meminfo(
        tmp_path,
        "MemTotal:       8388608 kB\n"     # 8 GiB
        "MemAvailable:  16777216 kB\n",    # 16 GiB — nonsensical but possible
    )
    snapshot = LinuxMemorySampler(mem_path=path).get_snapshot()

    assert snapshot.total_gb == 8.0
    assert snapshot.available_gb == 16.0
    assert snapshot.used_gb == -8.0
    assert snapshot.used_pct == -100.0


def test_memory_sampler_init_raises_on_missing_file(tmp_path):
    """Constructor health-check surfaces a missing file immediately."""
    with pytest.raises(FileNotFoundError):
        LinuxMemorySampler(mem_path=str(tmp_path / "does_not_exist"))


def test_memory_sampler_get_mem_data_raises_on_runtime_ioerror(tmp_path):
    """File vanishes after construction -> get_mem_data() raises.

    Was: get_mem_data swallowed IOError and returned {} (fatal path
    degraded into a zero snapshot). The refactor removes that catch so
    the missing file bubbles to LinuxCollector / main.py per rule 1.
    """
    path = _write_meminfo(tmp_path, "MemTotal: 16777216 kB\n")
    sampler = LinuxMemorySampler(mem_path=path)

    os.remove(path)

    with pytest.raises(FileNotFoundError):
        sampler.get_mem_data()

    with pytest.raises(FileNotFoundError):
        sampler.get_snapshot()