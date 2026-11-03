from engine.models import NetworkSnapshot
from dataclasses import dataclass
from engine.results_and_errors import Errors, InternalResult
import re
import time

# physical interfaces only
VALID_PREFIX = re.compile(r'^(eth|wlan|enp|eno|wlp|enx|ens|wlx|wwan|wwp|em|p[0-9])')


from engine.models import NetworkSnapshot
from engine.results_and_errors import Errors, InternalResult
import re
import time

# physical interfaces only
VALID_PREFIX = re.compile(r'^(eth|wlan|enp|eno|wlp|enx|ens|wlx|wwan|wwp|em|p[0-9])')


class LinuxNetworkSampler:
    def __init__(self, netdev_path: str = '/proc/net/dev'):
        self.netdev_path = netdev_path
        self._last_stats: dict[str, dict[str, int]] | None = None
        self._last_time: float | None = None
        self._last_error: Errors | None = None
        self._is_ready: bool = False

    # ------------------------------------------------------------------
    # State properties (used by the GUI/consumer to distinguish states)
    # ------------------------------------------------------------------
    @property
    def last_error(self) -> Errors | None:
        return self._last_error

    @property
    def is_ready(self) -> bool:
        """True once the sampler has successfully primed a baseline."""
        return self._is_ready

    @property
    def has_known_devices(self) -> bool:
        """True if we have ever seen an interface since instantiation."""
        return bool(self._last_stats)

    @property
    def is_primed(self) -> bool:
        """True once at least one snapshot has been taken (baseline stored)."""
        return self._last_stats is not None

    def _get_raw_stats(self) -> InternalResult:
        interfaces = {}
        try:
            with open(self.netdev_path, 'r') as f:
                lines = f.readlines()

                for line in lines[2:]:  # Skip headers
                    if not line.strip():
                        continue

                    if ":" in line:
                        interface, data = line.split(":", 1)
                        interface = interface.strip()

                        if VALID_PREFIX.match(interface):
                            try:
                                metrics = data.split()
                                interfaces[interface] = {
                                    "rx_bytes": int(metrics[0]),
                                    "rx_errs":  int(metrics[2]),
                                    "rx_drop":  int(metrics[3]),
                                    "tx_bytes": int(metrics[8]),
                                    "tx_errs":  int(metrics[10]),
                                    "tx_drop":  int(metrics[11])
                                }
                            except (IndexError, ValueError):
                                continue

            return InternalResult(data=interfaces)

        except FileNotFoundError:
            return InternalResult(error=Errors.FILE_NOT_FOUND)
        except PermissionError:
            return InternalResult(error=Errors.PERMISSION_DENIED)
        except Exception:
            return InternalResult(error=Errors.UNKNOWN)

    def get_network_snapshot(self) -> list[NetworkSnapshot]:
        current_time = time.monotonic()
        result = self._get_raw_stats()

        if result.error:
            self._last_error = result.error
            return []

        self._last_error = None
        current_stats = result.data or {}

        # First run: prime the baseline and return empty
        if self._last_stats is None or self._last_time is None:
            self._last_stats = current_stats
            self._last_time = current_time
            return []

        self._is_ready = True

        snapshots = []
        elapsed_time = max(0.001, current_time - self._last_time)
        all_interfaces = set(self._last_stats.keys()).union(current_stats.keys())

        for interface in sorted(all_interfaces):
            # State 1: Interface disconnected mid-session
            if interface not in current_stats:
                last = self._last_stats.get(interface, {})
                snapshots.append(NetworkSnapshot(
                    interface=interface,
                    status="DISCONNECTED",
                    download_bps=0.00,
                    upload_bps=0.00,
                    rx_errors=last.get("rx_errs", 0),
                    tx_errors=last.get("tx_errs", 0),
                    rx_drops=last.get("rx_drop", 0),
                    tx_drops=last.get("tx_drop", 0),
                    total_bytes=last.get("rx_bytes", 0) + last.get("tx_bytes", 0),
                ))
                continue
        
            # State 2: Interface freshly hot-plugged in mid-session
            if interface not in self._last_stats:
                stats_dict = current_stats.get(interface, {})
                rx = stats_dict.get("rx_bytes", 0)
                tx = stats_dict.get("tx_bytes", 0)
                
                snapshots.append(NetworkSnapshot(
                    interface=interface,
                    status="CONNECTING",
                    download_bps=0.00,
                    upload_bps=0.00,
                    rx_errors=stats_dict.get("rx_errs", 0),
                    tx_errors=stats_dict.get("tx_errs", 0),
                    rx_drops=stats_dict.get("rx_drop", 0),
                    tx_drops=stats_dict.get("tx_drop", 0),
                    total_bytes=rx + tx
                ))
                continue
            
            # State 3: Standard Operational Connected Calculations
            current = current_stats[interface]
            last = self._last_stats[interface]
            
            diff_rx = max(0, current["rx_bytes"] - last["rx_bytes"])
            diff_tx = max(0, current["tx_bytes"] - last["tx_bytes"])
            
            rx_bps = diff_rx / elapsed_time
            tx_bps = diff_tx / elapsed_time
            total_bytes = current["rx_bytes"] + current["tx_bytes"]
            
            snapshots.append(NetworkSnapshot(
                interface=interface,
                status="CONNECTED",
                download_bps=rx_bps,
                upload_bps=tx_bps,
                rx_errors=current['rx_errs'],
                tx_errors=current['tx_errs'],
                rx_drops=current['rx_drop'],
                tx_drops=current['tx_drop'],
                total_bytes=total_bytes
            ))
        
        # Preserve baseline across empty ticks so we keep emitting DISCONNECTED
        if current_stats:
            self._last_stats = current_stats
            self._last_time = current_time
        
        return snapshots