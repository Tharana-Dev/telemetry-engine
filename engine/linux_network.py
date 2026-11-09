import time
import psutil

from engine.models import NetworkSnapshot

class UniversalNetworkSampler:
    def __init__(self) -> None:
        self._last_net_stats = None
        self._last_time: float | None = None

    def get_network_snapshot(self) -> list[NetworkSnapshot]:
        current_time = time.monotonic()
        
        try:
            current_stats = psutil.net_io_counters(pernic=True)
            if_stats = psutil.net_if_stats()
        except Exception:
            return []

        if self._last_net_stats is None:
            self._last_net_stats = current_stats
            self._last_time = current_time
            return []

        duration = current_time - self._last_time
        snapshots = []

        if duration <= 0:
            return []

        for name, current in current_stats.items():
            # FIX: Removed "lo" from keywords. Use strict equality below.
            bad_keywords = ["loopback", "vethernet", "virtual", "wsl", "pseudo", "bluetooth"]
            
            # Strict equality for Linux/WSL loopback, substring match for the rest
            if name.lower() == "lo" or any(bad in name.lower() for bad in bad_keywords):
                continue

            if name not in self._last_net_stats:
                continue

            status = "CONNECTED" if (name in if_stats and if_stats[name].isup) else "DISCONNECTED"

            old = self._last_net_stats[name]

            down_delta = max(0, current.bytes_recv - old.bytes_recv)
            up_delta = max(0, current.bytes_sent - old.bytes_sent)

            download_bps = down_delta / duration
            upload_bps = up_delta / duration

            snapshots.append(NetworkSnapshot(
                interface=name,
                status=status,
                download_bps=download_bps,
                upload_bps=upload_bps,
                rx_errors=current.errin,
                tx_errors=current.errout,
                rx_drops=current.dropin,
                tx_drops=current.dropout,
                total_bytes=current.bytes_recv + current.bytes_sent
            ))

        self._last_net_stats = current_stats
        self._last_time = current_time

        return snapshots