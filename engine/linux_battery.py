from engine.models import BatterySnapshot
import os


class LinuxBatterySampler:
    def __init__(self, sys_path: str | None = "/sys/class/power_supply/") -> None:
        self.main_path = sys_path

        if not os.path.isdir(self.main_path):
            self.battery_path = None
            return

        # Look for the first battery and AC adapter entries. Some machines
        # don't expose an AC adapter at all (odd VMs, desktops), so we keep
        # those paths as None instead of assuming they exist.
        bat_folders = [f for f in sorted(os.listdir(self.main_path)) if f.startswith('BAT')]
        ac_folders = [f for f in sorted(os.listdir(self.main_path)) if f.startswith('AC')]

        self.battery_path = os.path.join(self.main_path, bat_folders[0]) if bat_folders else None
        self.ac_path = os.path.join(self.main_path, ac_folders[0]) if ac_folders else None

    def get_battery_snapshot(self) -> BatterySnapshot | None:
        # No battery at all — nothing to report. (Desktops, some VMs.)
        if self.battery_path is None:
            return None

        status = self._read_val("status") or "Unknown"

        # Figure out whether we're running on wall power. If there's an AC
        # adapter, trust its "online" file. Otherwise infer from the battery
        # status — some systems have no AC entry at all.
        if self.ac_path is not None:
            online = self._read_val("online", base_path=self.ac_path) == "1"
        else:
            online = status in ("Charging", "Full")

        # B9: missing capacity is None, not 0 (0% would look like a dead battery).
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
                # B2: some drivers report negative power; take magnitude.
                power_watts = abs(power) / 1_000_000  # µW -> W
            else:
                current = self._read_int("current_now")
                voltage = self._read_int("voltage_now")
                if current is not None and voltage is not None:
                    # µA * µV = pW -> W; sign of current varies by driver.
                    power_watts = abs(current * voltage) / 1_000_000_000_000

            # B1: only compute remaining time while actually discharging.
            # Do NOT trust `online` alone — USB-C charging quirks can leave
            # the AC adapter reporting online=0 while the battery is charging.
            if status == "Discharging" and power_watts is not None and power_watts > 0:
                hours_left = round(energy_now_converted / power_watts, 2)
        else:
            # Charge-based fallback. µAh / µA = hours — no voltage needed.
            charge_now = self._read_int("charge_now")
            current = self._read_int("current_now")
            if charge_now is not None and current is not None:
                current_abs = abs(current)
                # B1: again, gate on actual discharging state.
                if status == "Discharging" and current_abs > 0:
                    hours_left = round(charge_now / current_abs, 2)
            # power_watts stays None — no voltage available to compute watts.

        # B9: health is None if either capacity figure is missing; do not
        # pretend the battery is at 100% health.
        efull = self._read_int("energy_full")
        edesign = self._read_int("energy_full_design")
        if efull is None or edesign is None:
            cfull = self._read_int("charge_full")
            cdesign = self._read_int("charge_full_design")
            efull = cfull
            edesign = cdesign

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
        # Default base is the battery folder. Callers can pass an override
        # to read from the AC folder (for the "online" file).
        path = base_path if base_path is not None else self.battery_path
        if path is None:
            return None
        try:
            with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
                return f.read().strip()
        except (FileNotFoundError, OSError):
            return None

    def _read_int(self, filename: str) -> int | None:
        val = self._read_val(filename)
        if val is not None:
            try:
                return int(val)
            except ValueError:
                return None
        return None
