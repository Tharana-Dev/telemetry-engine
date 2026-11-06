import pytest
from engine.linux_network import LinuxNetworkSampler


MOCK_HEADER = (
    "Inter-|   Receive                                                |  Transmit\n"
    " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
)


def _write(tmp_path, content, name="net_dev"):
    p = tmp_path / name
    p.write_text(content)
    return str(p)


def _install_clock(monkeypatch, values):
    """Replace time.monotonic with a scripted sequence; hold the last value."""
    it = iter(values)
    last = {"v": values[-1]}

    def _clock():
        try:
            v = next(it)
            last["v"] = v
            return v
        except StopIteration:
            return last["v"]

    monkeypatch.setattr("engine.linux_network.time.monotonic", _clock)


def _make_sampler(tmp_path, monkeypatch, initial_content, times):
    path = _write(tmp_path, initial_content)
    _install_clock(monkeypatch, times)
    return LinuxNetworkSampler(netdev_path=path), path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_parsing_and_delta_math(tmp_path, monkeypatch):
    """Delta math over a 1.25s window with scheduling jitter."""
    t1 = MOCK_HEADER + (
        "  eth0: 1000000      50    2    1    0     0          0         0"
        "  2000000      40    4    2    0     0       0          0\n"
    )
    t2 = MOCK_HEADER + (
        "  eth0: 1012500      60    2    1    0     0          0         0"
        "  2005000      45    4    2    0     0       0          0\n"
    )

    sampler, path = _make_sampler(tmp_path, monkeypatch, t1, [100.0, 101.25])

    # First call only initialises the baseline — no snapshot yet.
    assert sampler.get_network_snapshot() == []

    _write(tmp_path, t2)                       # same file path, new contents
    results = sampler.get_network_snapshot()

    assert len(results) == 1
    eth0 = results[0]

    # NetworkSnapshot is a frozen dataclass → attribute access, not dict.
    assert eth0.interface == "eth0"
    assert eth0.status == "CONNECTED"

    # (1012500 - 1000000)/1.25 = 10,000 B/s
    assert eth0.download_bps == 10000
    # (2005000 - 2000000)/1.25 =  4,000 B/s
    assert eth0.upload_bps == 4000

    assert eth0.rx_errors == 2
    assert eth0.rx_drops == 1
    assert eth0.tx_errors == 4
    assert eth0.tx_drops == 2
    # 1012500 + 2005000 = 3,017,500 B
    assert eth0.total_bytes == 3017500


def test_interface_disconnect(tmp_path, monkeypatch):
    """An interface that disappears between snapshots is reported DISCONNECTED.

    Interfaces are tracked via the union of `_last_stats` keys and the
    current stats, so a vanished interface still gets a DISCONNECTED row.
    """
    t1 = MOCK_HEADER + (
        "  eth0:  1000   1   0   0   0   0   0   0    1000   1   0   0   0   0   0   0\n"
        "  wlan0: 50000  20  0   0   0   0   0   0    30000  10   0   0   0   0   0   0\n"
    )
    t2 = MOCK_HEADER + (
        "  eth0:  1000   1   0   0   0   0   0   0    1000   1   0   0   0   0   0   0\n"
    )

    sampler, _ = _make_sampler(tmp_path, monkeypatch, t1, [1.0, 2.0])
    sampler.get_network_snapshot()             # baseline

    _write(tmp_path, t2)
    results = sampler.get_network_snapshot()

    assert len(results) == 2
    by_iface = {r.interface: r for r in results}

    assert by_iface["eth0"].status == "CONNECTED"
    wlan = by_iface["wlan0"]
    assert wlan.status == "DISCONNECTED"
    assert wlan.download_bps == 0.00
    assert wlan.upload_bps == 0.00
    assert wlan.rx_errors == 0
    assert wlan.tx_errors == 0
    assert wlan.total_bytes == 80000


def test_counter_reset_edge_case(tmp_path, monkeypatch):
    """Counter rollback must clamp to 0 B/s, not produce negative speeds."""
    t1 = MOCK_HEADER + (
        "  eth0: 99999999  50  0  0  0  0  0  0  88888888  40  0  0  0  0  0  0\n"
    )
    t2 = MOCK_HEADER + (
        "  eth0:      450   1  0  0  0  0  0  0       200   1  0  0  0  0  0  0\n"
    )

    sampler, _ = _make_sampler(tmp_path, monkeypatch, t1, [1.0, 2.0])
    sampler.get_network_snapshot()

    _write(tmp_path, t2)
    results = sampler.get_network_snapshot()

    assert len(results) == 1
    eth0 = results[0]
    assert eth0.status == "CONNECTED"
    assert eth0.download_bps == 0.00
    assert eth0.upload_bps == 0.00


def test_hotplug_edge_case(tmp_path, monkeypatch):
    """An interface that appears mid-session is surfaced with zero speed.

    State 2 in `get_network_snapshot` labels this "CONNECTING"; the display
    branch in main.py keys off that literal, so the assertion below pins the
    contract between the two.
    """
    t1 = MOCK_HEADER + (
        "  eth0: 1000 1 0 0 0 0 0 0 1000 1 0 0 0 0 0 0\n"
    )
    t2 = MOCK_HEADER + (
        "  eth0: 1000 1 0 0 0 0 0 0 1000 1 0 0 0 0 0 0\n"
        "  enx001122334455: 2000 5 0 0 0 0 0 0 1000 2 0 0 0 0 0 0\n"
    )

    sampler, _ = _make_sampler(tmp_path, monkeypatch, t1, [1.0, 2.0])
    sampler.get_network_snapshot()

    _write(tmp_path, t2)
    results = sampler.get_network_snapshot()

    assert len(results) == 2
    by_iface = {r.interface: r for r in results}
    enx = by_iface["enx001122334455"]

    assert enx.status == "CONNECTING"
    assert enx.download_bps == 0.00
    assert enx.upload_bps == 0.00
    assert enx.total_bytes == 3000         # (2000 + 1000) bytes


def test_missing_netdev_file_raises(tmp_path, monkeypatch):
    """Fatal: /proc/net/dev missing -> FileNotFoundError bubbles.

    Was: swallowed into InternalResult(Errors.FILE_NOT_FOUND) and turned
    into an empty return list. Now the open() call is fatal.
    """
    _install_clock(monkeypatch, [1.0, 2.0])
    sampler = LinuxNetworkSampler(netdev_path=str(tmp_path / "nope"))

    with pytest.raises(FileNotFoundError):
        sampler.get_network_snapshot()


def test_no_valid_interfaces_returns_empty_list(tmp_path, monkeypatch):
    """No hardware: file exists but no matching physical interfaces -> [].

    First tick always returns [] anyway (baseline priming); this test drives
    a second tick with no matching interfaces to confirm the empty-list
    no-hardware path.
    """
    t = MOCK_HEADER + (
        "    lo: 100 1 0 0 0 0 0 0 100 1 0 0 0 0 0 0\n"  # lo is filtered out
    )

    sampler, path = _make_sampler(tmp_path, monkeypatch, t, [1.0, 2.0])
    assert sampler.get_network_snapshot() == []   # baseline

    _write(tmp_path, t)                           # same content, second tick
    assert sampler.get_network_snapshot() == []