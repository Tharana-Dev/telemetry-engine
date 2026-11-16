from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AlertId(StrEnum):
    """Unique rule identifiers used for debouncing, cooldowns, and clearing."""
    CPU_HIGH = "cpu_high"
    CPU_TEMP_HIGH = "cpu_temp_high"
    DISK_SPACE_LOW = "disk_space_low" 
    DISK_LOW = "disk_low"
    BATTERY_LOW = "battery_low"
    BATTERY_CRITICAL = "battery_critical"
    NETWORK_DISCONNECTED = "network_disconnected"


class AlertSource(StrEnum):
    """Hardware sector tags displayed as [TAG] badges in the notification feed."""
    CPU = "CPU"
    MEMORY = "MEMORY"
    DISK = "DISK"
    BATTERY = "BATTERY"
    NETWORK = "NETWORK"
    THERMAL = "THERMAL"


class AlertSeverity(StrEnum):
    """Alert urgency tiers used for badge color-coding."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Notification:
    """Immutable, thread-safe alert payload emitted by NotificationWorker."""
    id: AlertId
    source: AlertSource
    message: str
    severity: AlertSeverity = AlertSeverity.WARNING
    timestamp: datetime = field(default_factory=datetime.now)
