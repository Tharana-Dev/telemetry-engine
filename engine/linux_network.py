from engine.models import NetworkSnapshot
import re
import time

VALID_PREFIX = re.compile(r'^(eth|wlan|enp|eno|wlp|enx|ens|wlx|wwan|wwp|em|p[0-9])')

class LinuxNetworkSampler:
    def __init__(self, netdev_path: str = '/proc/net/dev'):
        self.netdev_path = netdev_path
        self._last_stats: dict[str, dict[str, int]] | None = None
        self._last_time: float | None = None

    def _get_raw_stats(self) -> dict[str, dict[str, int]] | None:
        interfaces: dict[str, dict[str, int]] = {}
        try:
            with open(self.netdev_path, 'r') as f:
                lines = f.readlines()
        except Exception:
            return None

        for line in lines[2:]:
            if not line.strip() or ":" not in line:
                continue
            interface, data = line.split(":", 1)
            interface = interface.strip()

            if not VALID_PREFIX.match(interface):
                continue

            try:
                metrics = data.split()
                interfaces[interface] = {
                    "rx_bytes": int(metrics[0]),
                    "rx_errs":  int(metrics[2]),
                    "rx_drop":  int(metrics[3]),
                    "tx_bytes": int(metrics[8]),
                    "tx_errs":  int(metrics[10]),
                    "tx_drop":  int(metrics[11]),
                }
            except (IndexError, ValueError):
                continue

        return interfaces if interfaces else None

    def get_network_snapshot(self) -> list[NetworkSnapshot] | None:
        current_time = time.monotonic()
        current_stats = self._get_raw_stats()

        # NO HARDWARE / FAILURE
        if not current_stats:
            return None

        # INITIALIZING (First Tick)
        if self._last_stats is None or self._last_time is None:
            self._last_stats = current_stats
            self._last_time = current_time
            return []

        snapshots: list[NetworkSnapshot] = []
        elapsed_time = max(0.001, current_time - self._last_time)
        all_interfaces = set(self._last_stats.keys()).union(current_stats.keys())

        for interface in sorted(all_interfaces):
            if interface not in current_stats:
                last = self._last_stats.get(interface, {})
                snapshots.append(NetworkSnapshot(
                    interface=interface, status="DISCONNECTED",
                    download_bps=0.00, upload_bps=0.00,
                    rx_errors=last.get("rx_errs", 0), tx_errors=last.get("tx_errs", 0),
                    rx_drops=last.get("rx_drop", 0), tx_drops=last.get("tx_drop", 0),
                    total_bytes=last.get("rx_bytes", 0) + last.get("tx_bytes", 0),
                ))
                continue

            if interface not in self._last_stats:
                stats_dict = current_stats.get(interface, {})
                rx = stats_dict.get("rx_bytes", 0)
                tx = stats_dict.get("tx_bytes", 0)
                snapshots.append(NetworkSnapshot(
                    interface=interface, status="CONNECTING",
                    download_bps=0.00, upload_bps=0.00,
                    rx_errors=stats_dict.get("rx_errs", 0), tx_errors=stats_dict.get("tx_errs", 0),
                    rx_drops=stats_dict.get("rx_drop", 0), tx_drops=stats_dict.get("tx_drop", 0),
                    total_bytes=rx + tx,
                ))
                continue

            current = current_stats[interface]
            last = self._last_stats[interface]

            diff_rx = max(0, current["rx_bytes"] - last["rx_bytes"])
            diff_tx = max(0, current["tx_bytes"] - last["tx_bytes"])

            snapshots.append(NetworkSnapshot(
                interface=interface, status="CONNECTED",
                download_bps=diff_rx / elapsed_time, upload_bps=diff_tx / elapsed_time,
                rx_errors=current['rx_errs'], tx_errors=current['tx_errs'],
                rx_drops=current['rx_drop'], tx_drops=current['tx_drop'],
                total_bytes=current["rx_bytes"] + current["tx_bytes"],
            ))

        self._last_stats = current_stats
        self._last_time = current_time

        # If snapshots is empty, return None
        return snapshots if snapshots else None