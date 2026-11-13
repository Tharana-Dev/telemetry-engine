import ctypes
from dataclasses import dataclass
from enum import Enum, auto
import getpass
import os
import platform
import re
import socket
import sys
import time
import psutil

_PHYSICAL_NIC_PATTERN = re.compile(
    r"^(?:"
    r"wi-?fi|wlan\d*|wlp\w+|"
    r"ethernet(?:\s*\d+)?|eth\d+|enp\w+|eno\w+|ens\w+|"
    r"en\d+|"
    r"local area connection(?:\s*\d+)?"
    r")$",
    re.IGNORECASE,
)


class DeviceType(Enum):
    LAPTOP = auto()
    DESKTOP = auto()
    UNKNOWN = auto()

    @property
    def label(self) -> str:
        labels = {
            DeviceType.LAPTOP: "Laptop Workstation",
            DeviceType.DESKTOP: "Desktop Workstation",
            DeviceType.UNKNOWN: "Unknown System",
        }
        return labels[self]


@dataclass(frozen=True)
class SystemProfile:
    # Identity & OS
    device_type: DeviceType
    os_name: str
    os_release: str
    hostname: str
    username: str          # ← NEW

    # Hardware Baseline
    cpu_summary: str
    ram_total_gb: int
    uptime_hours: float

    # Power Context
    has_battery: bool
    power_source: str
    battery_percent: int | None

    # Pre-Flight Readiness
    is_admin: bool
    net_sensors_ok: bool
    net_interface: str


class GetData:

    def collect(self) -> SystemProfile:
        """Collects all system telemetry and returns an immutable SystemProfile."""
        device_type, has_battery, power_source, battery_percent = (
            self._detect_device_and_power()
        )
        net_ok, nic_name = self._check_network_status()

        raw_os = platform.system()
        os_name = "macOS" if raw_os == "Darwin" else raw_os

        cpu_summary = platform.processor() or platform.machine() or "Unknown CPU"
        ram_total_gb = round(psutil.virtual_memory().total / (1024**3))
        uptime_hours = round((time.time() - psutil.boot_time()) / 3600, 1)

        return SystemProfile(
            device_type=device_type,
            os_name=os_name,
            os_release=platform.release(),
            hostname=socket.gethostname(),
            username=self._get_username(),
            cpu_summary=cpu_summary,
            ram_total_gb=ram_total_gb,
            uptime_hours=uptime_hours,
            has_battery=has_battery,
            power_source=power_source,
            battery_percent=battery_percent,
            is_admin=self._check_is_admin(),
            net_sensors_ok=net_ok,
            net_interface=nic_name,
        )

    def _get_username(self) -> str:
        """Fetches the Windows Display Name natively via netapi32 (no subprocess)."""
        if sys.platform == "win32":
            try:
                import getpass
                from ctypes import wintypes

                # Define the struct Windows uses to return user info
                class USER_INFO_10(ctypes.Structure):
                    _fields_ = [
                        ("usri10_name", wintypes.LPWSTR),
                        ("usri10_comment", wintypes.LPWSTR),
                        ("usri10_usr_comment", wintypes.LPWSTR),
                        ("usri10_full_name", wintypes.LPWSTR),
                    ]

                raw_user = getpass.getuser()
                bufptr = ctypes.c_void_p()
                netapi32 = ctypes.windll.netapi32

                # Ask Windows for Level 10 info (which includes the Display Name)
                res = netapi32.NetUserGetInfo(None, raw_user, 10, ctypes.byref(bufptr))
                
                if res == 0:  # 0 means success
                    info = ctypes.cast(bufptr, ctypes.POINTER(USER_INFO_10)).contents
                    full_name = info.usri10_full_name
                    
                    # Free the memory Windows allocated for the struct
                    netapi32.NetApiBufferFree(bufptr)
                    
                    if full_name and full_name.strip():
                        return full_name.strip()
            except Exception:
                pass  # Silently fall back if the API call fails

        # Fallback for macOS/Linux or if the API fails
        name = ""
        try:
            name = psutil.Process().username() or ""
        except Exception:
            pass
        if not name:
            try:
                name = getpass.getuser() or ""
            except Exception:
                pass
        
        if "\\" in name:
            name = name.rsplit("\\", 1)[-1]
        
        name = name.strip() or "User"
        return name[:1].upper() + name[1:]
    
    
    def _detect_device_and_power(
        self,
    ) -> tuple[DeviceType, bool, str, int | None]:
        try:
            battery = psutil.sensors_battery()

            if battery is None:
                return (DeviceType.DESKTOP, False, "Mains AC", None)

            is_plugged = bool(battery.power_plugged)
            power_source = "AC Power" if is_plugged else "Battery"
            percent = (
                round(battery.percent) if battery.percent is not None else None
            )
            return (DeviceType.LAPTOP, True, power_source, percent)

        except Exception:
            return (DeviceType.UNKNOWN, False, "Unknown", None)

    def _check_is_admin(self) -> bool:
        if sys.platform != "win32":
            return os.geteuid() == 0
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _check_network_status(self) -> tuple[bool, str]:
        try:
            for nic_name, stats in psutil.net_if_stats().items():
                if _PHYSICAL_NIC_PATTERN.match(nic_name.strip()) and stats.isup:
                    return True, nic_name
        except Exception:
            pass

        return False, "Offline"