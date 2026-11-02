from engine.models import NetworkSnapshot
from dataclasses import dataclass
from engine.results_and_errors import Errors, InternalResult
import re
import time

# physical interfaces only
VALID_PREFIX = re.compile(r'^(eth|wlan|enp|eno|wlp|enx)')


class LinuxNetworkSampler:
    def __init__(self, netdev_path: str = '/proc/net/dev'):
        self.netdev_path = netdev_path
        self._last_stats = None
        self._last_time = None
        self.count = 1

    def _get_raw_stats(self):
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
                            metrics = data.split()
                            interfaces[interface] = {
                                "rx_bytes": int(metrics[0]),
                                "rx_errs":  int(metrics[2]),
                                "rx_drop":  int(metrics[3]),
                                "tx_bytes": int(metrics[8]),
                                "tx_errs":  int(metrics[10]),
                                "tx_drop":  int(metrics[11])
                            }

            return InternalResult(data=interfaces)

        except FileNotFoundError:
            return InternalResult(error=Errors.FILE_NOT_FOUND)

    def get_network_snapshot(self):
        current_time = time.monotonic()
        result = self._get_raw_stats()

        if result.error or not result.data:
            return []

        current_stats = result.data

        if self._last_stats is None or self._last_time is None:
            self._last_stats = current_stats
            self._last_time = current_time
            return []

        snapshots = []
        elapsed_time = max(0.001, current_time - self._last_time)
        all_interfaces = set(self._last_stats.keys()
                             ).union(current_stats.keys())

        for interface in sorted(all_interfaces):
            # State 1: Interface disconnected mid-session
            if interface not in current_stats:
                snapshots.append(NetworkSnapshot(
                    interface= interface,
                    status= "CONNECTING",
                    download_mbps= 0.00,
                    upload_mbps= 0.00,
                    rx_errors= 0,
                    tx_errors= 0,
                    rx_drops= 0,
                    tx_drops= 0,
                    total_gb=0.00
                ))
                
                continue
        
            # State 2: Interface freshly hot-plugged in mid-session
            if interface not in self._last_stats:
                if isinstance(current_stats, dict):
                    # 1. Safely grab the interface dict, defaulting to an empty dict
                    stats_dict: dict[str, int] = current_stats.get(interface, {})
                    rx = stats_dict.get("rx_bytes", 0)
                    tx = stats_dict.get("tx_bytes", 0)
                    total_bytes = rx + tx
                    
                snapshots.append(NetworkSnapshot(
                    interface= interface,
                    status= "DISCONNECTED",
                    download_mbps= 0.00,
                    upload_mbps= 0.00,
                    rx_errors= 0,
                    tx_errors= 0,
                    rx_drops= 0,
                    tx_drops= 0,
                    total_gb=total_bytes
                ))
                
                continue
            
            # State 3: Standard Operational Connected Calculations
            deltas = {}
            if isinstance(current_stats, dict) and isinstance(self._last_stats, dict):
                for key in ["rx_bytes", "tx_bytes"]:
                    diff = current_stats[interface][key] - self._last_stats[interface][key]
                    deltas[key] = max(0, diff) # Safe rollback clamping logic
                
                rx_bps = deltas["rx_bytes"] / elapsed_time
                tx_bps = deltas["tx_bytes"] / elapsed_time
                
                total_bytes = current_stats[interface]["rx_bytes"] + current_stats[interface]["tx_bytes"]
                
                rx_issue = current_stats[interface]['rx_errs']
                rx_drop = current_stats[interface]['rx_drop']
                tx_issue = current_stats[interface]['tx_errs']
                tx_drop = current_stats[interface]['tx_drop']
                
                snapshots.append(NetworkSnapshot(
                    interface= interface,
                    status= "CONNECTED",
                    download_mbps= rx_bps,
                    upload_mbps= tx_bps,
                    rx_errors= rx_issue,
                    tx_errors= tx_issue,
                    rx_drops= rx_drop,
                    tx_drops= tx_drop,
                    total_gb=total_bytes
                ))
        
        self._last_stats = current_stats
        self._last_time = current_time
        
        return snapshots