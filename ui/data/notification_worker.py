import threading
import time

from PySide6.QtCore import QObject, Signal

from engine.logger import logger
from ui.models.get_sampler import get_sampler
from ui.models.notification import (
    AlertId,
    AlertSeverity,
    AlertSource,
    Notification,
)


# ---------------------------------------------------------------------------
# Snapshot accessors — match the real samplers in engine/samplers/.
# ---------------------------------------------------------------------------

def _get(obj, *names, default=None):
    if obj is None:
        return default
    for n in names:
        if isinstance(obj, dict):
            if n in obj:
                return obj[n]
        elif hasattr(obj, n):
            return getattr(obj, n)
    return default


def _as_list(snapshot):
    if snapshot is None:
        return []
    if isinstance(snapshot, (list, tuple)):
        return list(snapshot)
    return [snapshot]


def _cpu_usage(snap):
    v = _get(snap, "usage_pct")
    return float(v) if isinstance(v, (int, float)) else None

def _memory_pct(mem):
    v = _get(mem, "used_pct")
    return float(v) if isinstance(v, (int, float)) else None

def _cpu_temp(thermal):
    if thermal is None:
        return None
    v = _get(thermal, "cpu_temp")
    return float(v) if isinstance(v, (int, float)) else None


def _partition_free_pct(p):
    used_pct = _get(p, "percent")
    if used_pct is not None:
        return 100.0 - float(used_pct)
    free = _get(p, "free_bytes")
    total = _get(p, "total_bytes")
    if free is not None and total:
        return 100.0 * free / total
    return None


def _iface_up(i):
    return _get(i, "status") == "CONNECTED"


def _battery_pct(b):
    v = _get(b, "capacity")
    return float(v) if isinstance(v, (int, float)) else None


def _battery_on_ac(b):
    v = _get(b, "online", default=True)
    return bool(v)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class NotificationWorker(QObject):
    finished = Signal()
    notification_added = Signal(object)    # Notification
    notification_cleared = Signal(object)  # AlertId

    def __init__(self):
        super().__init__()

        self._stop_event = threading.Event()

        # --- alert state ---
        self._strikes: dict[AlertId, int] = {}
        self._cooldowns: dict[AlertId, float] = {}
        self._active_alerts: dict[AlertId, Notification] = {}

        # --- cadence ---
        self._poll_interval = 3.0
        self._strike_threshold = 10       # 10 * 3s = 30s sustained
        self._cooldown_seconds = 300      # 5 min

        # --- thresholds ---
        self._cpu_pct = 85.0
        self._cpu_temp_c = 85.0
        self._memory_pct = 85.0
        self._disk_low_pct = 15.0         # warning tier
        self._disk_space_low_pct = 5.0    # critical tier
        self._battery_low_pct = 20.0      # warning tier
        self._battery_critical_pct = 5.0  # critical tier

        try:
            self._data = get_sampler()
        except Exception as e:
            logger.error(f"Failed to initialize collector: {e}")
            self._data = None

    # ---------------- helpers ----------------

    def _can_fire(self, alert_id: AlertId) -> bool:
        last = self._cooldowns.get(alert_id)
        if last is None:
            return True
        return (time.monotonic() - last) > self._cooldown_seconds

    def _start_cooldown(self, alert_id: AlertId) -> None:
        self._cooldowns[alert_id] = time.monotonic()

    def _sustained_s(self) -> int:
        return int(self._strike_threshold * self._poll_interval)

    def _evaluate(
        self,
        alert_id: AlertId,
        source: AlertSource,
        make_message,
        severity: AlertSeverity,
    ) -> None:
        """Count a strike; fire if sustained long enough and cooldown allows."""
        self._strikes[alert_id] = self._strikes.get(alert_id, 0) + 1
        if (
            self._strikes[alert_id] >= self._strike_threshold
            and self._can_fire(alert_id)
        ):
            notif = Notification(
                id=alert_id,
                source=source,
                message=make_message(),
                severity=severity,
            )
            self.notification_added.emit(notif)
            self._start_cooldown(alert_id)
            self._active_alerts[alert_id] = notif

    def _clear(self, alert_id: AlertId) -> None:
        """Reset strikes and clear an active alert tier (no-op if not active)."""
        self._strikes[alert_id] = 0
        if alert_id in self._active_alerts:
            del self._active_alerts[alert_id]
            self.notification_cleared.emit(alert_id)

    # ---------------- per-metric checks ----------------

    def _check_cpu(self, cpu) -> None:
        usage = _cpu_usage(cpu)
        if usage is None:
            return
        if usage > self._cpu_pct:
            self._evaluate(
                AlertId.CPU_HIGH,
                AlertSource.CPU,
                lambda: (
                    f"CPU usage above {self._cpu_pct:.0f}% "
                    f"for {self._sustained_s()}s."
                ),
                AlertSeverity.WARNING,
            )
        else:
            self._clear(AlertId.CPU_HIGH)

    def _check_memory(self, memory) -> None:
        pct = _memory_pct(memory)
        if pct is None:
            return
        if pct > self._memory_pct:
            self._evaluate(
                AlertId.MEMORY_HIGH,
                AlertSource.MEMORY,
                lambda: (
                    f"Memory usage above {self._memory_pct:.0f}% "
                    f"for {self._sustained_s()}s."
                ),
                AlertSeverity.WARNING,
            )
        else:
            self._clear(AlertId.MEMORY_HIGH)

    def _check_cpu_temp(self, thermal) -> None:
        temp = _cpu_temp(thermal)
        if temp is None:
            # Sensor unavailable (no admin / WinTmp missing / WMI failed).
            # Skip rather than fire — the UI surfaces sensor_error separately.
            return
        if temp > self._cpu_temp_c:
            self._evaluate(
                AlertId.CPU_TEMP_HIGH,
                AlertSource.THERMAL,
                lambda: (
                    f"CPU temperature at {temp:.0f}°C "
                    f"for {self._sustained_s()}s."
                ),
                AlertSeverity.CRITICAL,
            )
        else:
            self._clear(AlertId.CPU_TEMP_HIGH)

    def _check_disk_space(self, disk_space) -> None:
        parts = [p for p in _as_list(disk_space) if _partition_free_pct(p) is not None]
        if not parts:
            return
        worst = min(parts, key=_partition_free_pct)
        pct = _partition_free_pct(worst)

        if pct < self._disk_space_low_pct:
            # critical tier → clear warning, fire critical
            self._clear(AlertId.DISK_LOW)
            self._evaluate(
                AlertId.DISK_SPACE_LOW,
                AlertSource.DISK,
                lambda: f"System disk critically low: {pct:.1f}% free.",
                AlertSeverity.CRITICAL,
            )
        elif pct < self._disk_low_pct:
            # warning tier → clear critical (downgrade), fire warning
            self._clear(AlertId.DISK_SPACE_LOW)
            self._evaluate(
                AlertId.DISK_LOW,
                AlertSource.DISK,
                lambda: f"System disk low on space: {pct:.1f}% free.",
                AlertSeverity.WARNING,
            )
        else:
            # healthy → clear both
            self._clear(AlertId.DISK_LOW)
            self._clear(AlertId.DISK_SPACE_LOW)

    def _check_battery(self, battery) -> None:
        pct = _battery_pct(battery)
        if pct is None:
            return
        discharging = not _battery_on_ac(battery)

        if not discharging:
            # plugged in / unknown → clear both tiers
            self._clear(AlertId.BATTERY_LOW)
            self._clear(AlertId.BATTERY_CRITICAL)
        elif pct < self._battery_critical_pct:
            # critical tier → clear warning, fire critical
            self._clear(AlertId.BATTERY_LOW)
            self._evaluate(
                AlertId.BATTERY_CRITICAL,
                AlertSource.BATTERY,
                lambda: f"Battery critically low at {pct:.0f}%.",
                AlertSeverity.CRITICAL,
            )
        elif pct < self._battery_low_pct:
            # warning tier → clear critical (downgrade), fire warning
            self._clear(AlertId.BATTERY_CRITICAL)
            self._evaluate(
                AlertId.BATTERY_LOW,
                AlertSource.BATTERY,
                lambda: f"Battery low at {pct:.0f}%.",
                AlertSeverity.WARNING,
            )
        else:
            # healthy → clear both
            self._clear(AlertId.BATTERY_LOW)
            self._clear(AlertId.BATTERY_CRITICAL)

    def _check_network(self, net_list) -> None:
        ifaces = _as_list(net_list)
        if not ifaces:
            return  # no data or priming cycle — don't fire
        any_up = any(_iface_up(i) for i in ifaces)
        if any_up:
            self._clear(AlertId.NETWORK_DISCONNECTED)
        else:
            self._evaluate(
                AlertId.NETWORK_DISCONNECTED,
                AlertSource.NETWORK,
                lambda: "All network interfaces are down.",
                AlertSeverity.WARNING,
            )

    # ---------------- lifecycle ----------------

    def stop(self) -> None:
        self._stop_event.set()

    def work(self) -> None:
        try:
            if self._data is None:
                return

            # Startup spike wait
            if self._stop_event.wait(2.0):
                return

            # Prime every sampler once so first deltas aren't garbage
            self._data.get_cpu_snapshot()
            self._data.get_memory_snapshot()
            self._data.get_disk_io_snapshot()
            self._data.get_network_snapshot()
            self._data.get_battery_snapshot()
            self._data.get_disk_space_snapshot()
            self._data.get_thermal_snapshot()
            if self._stop_event.wait(0.1):
                return

            while not self._stop_event.is_set():
                cpu = self._data.get_cpu_snapshot()
                thermal = self._data.get_thermal_snapshot()
                disk_space = self._data.get_disk_space_snapshot()
                battery = self._data.get_battery_snapshot()
                net_list = self._data.get_network_snapshot()
                memory = self._data.get_memory_snapshot()

                # Keep memory + disk I/O samplers warm; no checks yet
                self._data.get_memory_snapshot()
                self._data.get_disk_io_snapshot()

                self._check_cpu(cpu)
                self._check_memory(memory) 
                self._check_cpu_temp(thermal)
                self._check_disk_space(disk_space)
                self._check_battery(battery)
                self._check_network(net_list)

                self._stop_event.wait(self._poll_interval)
        except Exception as e:
            logger.error(f"NotificationWorker crashed: {e}")
        finally:
            self.finished.emit()