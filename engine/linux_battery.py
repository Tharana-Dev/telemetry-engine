from engine.models import BatterySnapshot
import os


class LinuxBatterySampler:
    def __init__(self, sys_path: str | None = "/sys/class/power_supply/") -> None:
        self.main_path = sys_path
        self.battery_path: str | None = None
        self.ac_path: str | None = None

        # Explicit None = sampling disabled by caller.
        if sys_path is None:
            return

        # Fatal: if /sys/class/power_supply/ is missing or unreadable,
        # os.listdir raises FileNotFoundError / PermissionError and we let
        # it bubble up to the LinuxCollector.
        entries = sorted(os.listdir(self.main_path))

        bat_folders: list[str] = []
        ac_folders: list[str] = []

        # Read the `type` file inside each folder instead of relying on the
        # name prefix — USB-C chargers show up as e.g. ucsi-source-psy-*.
        for name in entries:
            folder = os.path.join(self.main_path, name)
            if not os.path.isdir(folder):
                continue

            type_val = self._read_val("type", base_path=folder)

            if type_val == "Battery":
                # Skip device-scoped batteries (wireless mice, keyboards).
                if self._is_peripheral(folder):
                    continue
                bat_folders.append(name)
            elif type_val == "Mains":
                ac_folders.append(name)

        # Fall back to name matching if the type files were missing.
        if not bat_folders:
            bat_folders = [
                f for f in entries
                if "BAT" in f
                and not self._is_peripheral(os.path.join(self.main_path, f))
            ]

        if not ac_folders:
            ac_folders = [
                f for f in entries
                if f.startswith("AC") or f.startswith("ADP") or "ucsi" in f
            ]

        self.battery_path = os.path.join(self.main_path, bat_folders[0]) if bat_folders else None
        self.ac_path = os.path.join(self.main_path, ac_folders[0]) if ac_folders else None

    def _is_peripheral(self, folder: str) -> bool:
        """True for device-scoped batteries (wireless mice, keyboards, controllers).

        System batteries have scope='System' or no scope file at all (older
        kernels). Peripherals always set scope='Device'.
        """
        return self._read_val("scope", base_path=folder) == "Device"

    def get_battery_snapshot(self) -> BatterySnapshot | None:
        # No hardware: desktop, VM, or no system battery present.
        if self.battery_path is None:
            return None

        # Partial errors below: any individual field that can't be read is
        # None. No exceptions, no "Unknown" fallback.
        status = self._read_val("status")

        # Prefer the AC adapter's "online" file; otherwise infer from
        # battery status. If neither is readable, online is None.
        ac_val = (
            self._read_val("online", base_path=self.ac_path)
            if self.ac_path is not None
            else None
        )
        if ac_val is not None:
            online = ac_val == "1"
        elif status is not None:
            # Include "Not charging" so a charge-limited battery on wall
            # power isn't misreported as offline.
            online = status in ("Charging", "Full", "Not charging")
        else:
            online = None

        # Missing capacity is None, not 0 (0% would look like a dead battery).
        capacity = self._read_int("capacity")

        power_watts: float | None = None
        hours_left: float | None = None

        # Linux exposes two flavours of batteries in sysfs:
        #   1. Energy-based: energy_now (µWh), power_now (µW)
        #   2. Charge-based: charge_now (µAh), current_now (µA)
        energy_now = self._read_int("energy_now")
        if energy_now is not None:
            energy_now_converted = energy_now / 1_000_000  # µWh -> Wh

            power = self._read_int("power_now")
            if power is not None:
                # Some drivers report negative power; take magnitude.
                power_watts = abs(power) / 1_000_000  # µW -> W
            else:
                current = self._read_int("current_now")
                voltage = self._read_int("voltage_now")
                if current is not None and voltage is not None:
                    # µA * µV = pW -> W; sign of current varies by driver.
                    power_watts = abs(current * voltage) / 1_000_000_000_000

            # Only compute remaining time while actually discharging —
            # don't trust `online` alone, USB-C quirks can lie.
            if status == "Discharging" and power_watts is not None and power_watts > 0:
                hours_left = round(energy_now_converted / power_watts, 2)
        else:
            # Charge-based fallback. µAh / µA = hours — no voltage needed.
            charge_now = self._read_int("charge_now")
            current = self._read_int("current_now")
            voltage = self._read_int("voltage_now")

            if charge_now is not None and current is not None:
                current_abs = abs(current)
                if status == "Discharging" and current_abs > 0:
                    hours_left = round(charge_now / current_abs, 2)

            # µA * µV = pW -> W.
            if current is not None and voltage is not None:
                power_watts = abs(current * voltage) / 1_000_000_000_000

        # Health is None if either capacity figure is missing; do not
        # pretend the battery is at 100% health.
        efull = self._read_int("energy_full")
        edesign = self._read_int("energy_full_design")
        if efull is None or edesign is None:
            efull = self._read_int("charge_full")
            edesign = self._read_int("charge_full_design")

        if efull is not None and edesign is not None and edesign > 0:
            health_percent: float | None = min(round((efull / edesign) * 100, 1), 100.0)
        else:
            health_percent = None

        return BatterySnapshot(
            online=online,
            status=status,
            capacity=capacity,
            power_watts=power_watts,
            hours_left=hours_left,
            health_percent=health_percent,
        )

    def _read_val(self, filename: str, base_path: str | None = None) -> str | None:
        # Default base is the battery folder; callers can override for the
        # AC folder or discovery files. Any per-file read failure is partial
        # (FileNotFoundError / PermissionError / NotADirectoryError, all
        # OSError subclasses) -> None.
        path = base_path if base_path is not None else self.battery_path
        if path is None:
            return None
        try:
            with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
                return f.read().strip()
        except OSError:
            return None

    def _read_int(self, filename: str) -> int | None:
        val = self._read_val(filename)
        if val is not None:
            try:
                return int(val)
            except ValueError:
                return None
        return None