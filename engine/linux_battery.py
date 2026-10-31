from engine.models import BatterySnapshot
import os


class LinuxBatterySampler:
    def __init__(self, sys_path: str | None = "/sys/class/power_supply/") -> None:
        self.main_path = sys_path

        # Look for the first battery and AC adapter entries. Some machines
        # don't expose an AC adapter at all (odd VMs, desktops), so we keep
        # those paths as None instead of assuming they exist.
        bat_folders = [f for f in os.listdir(self.main_path) if f.startswith('BAT')]
        ac_folders = [f for f in os.listdir(self.main_path) if f.startswith('AC')]

        self.battery_path = os.path.join(self.main_path, bat_folders[0]) if bat_folders else None
        self.ac_path = os.path.join(self.main_path, ac_folders[0]) if ac_folders else None

    def get_battery_snapshot(self) -> BatterySnapshot | None:
        # No battery at all — nothing to report. (Desktops, some VMs.)
        if self.battery_path is None:
            return None

        # Battery status, e.g. "Charging", "Discharging", "Full", "Not charging".
        status = self._read_val("status") or "Unknown"

        # Figure out whether we're running on wall power. If there's an AC
        # adapter, trust its "online" file. Otherwise infer from the battery
        # status — some systems have no AC entry at all.
        if self.ac_path is not None:
            online = self._read_val("online", base_path=self.ac_path) == "1"
        else:
            online = status in ("Charging", "Full")

        # Battery charge percentage. Missing file -> treat as 0, don't crash.
        capacity_str = self._read_val("capacity")
        capacity = int(capacity_str) if capacity_str is not None else 0

        power_watts = 0.0
        hours_left = 0.0

        # Linux exposes two flavours of batteries in sysfs:
        #   1. Energy-based: energy_now (µWh), power_now (µW)
        #   2. Charge-based: charge_now (µAh), current_now (µA)
        # Try energy first, fall back to charge. Both are common in the wild.
        energy_now_str = self._read_val("energy_now")
        if energy_now_str is not None:
            energy_now = int(energy_now_str) / 1_000_000  # µWh -> Wh

            # Prefer power_now if present — it's already in watts.
            power_str = self._read_val("power_now")
            if power_str is not None:
                power_watts = int(power_str) / 1_000_000  # µW -> W
            else:
                # Some drivers only expose current & voltage; derive power.
                current_str = self._read_val("current_now")
                voltage_str = self._read_val("voltage_now")
                if current_str is not None and voltage_str is not None:
                    # µA * µV = pW, so divide by 1e12 to get W.
                    power_watts = (
                        int(current_str) * int(voltage_str)
                    ) / 1_000_000_000_000

            # Time remaining only makes sense while discharging.
            if power_watts > 0 and not online:
                hours_left = round(energy_now / power_watts, 2)
        else:
            # Charge-based fallback. We can still get hours_left directly,
            # because µAh / µA = hours — no voltage needed.
            charge_now_str = self._read_val("charge_now")
            current_str = self._read_val("current_now")
            if charge_now_str is not None and current_str is not None:
                charge_now = int(charge_now_str)
                current = int(current_str)
                if current > 0 and not online:
                    hours_left = round(charge_now / current, 2)
            # power_watts stays 0 here — no voltage available to compute watts.

        # Health = full capacity vs. design capacity, as a percentage.
        # Try the energy pair first, then the charge pair; both give a ratio.
        efull_str = self._read_val("energy_full")
        edesign_str = self._read_val("energy_full_design")
        if efull_str is not None and edesign_str is not None:
            efull = int(efull_str)
            edesign = int(edesign_str)
        else:
            cfull_str = self._read_val("charge_full")
            cdesign_str = self._read_val("charge_full_design")
            efull = int(cfull_str) if cfull_str is not None else 0
            edesign = int(cdesign_str) if cdesign_str is not None else 0

        # Avoid divide-by-zero on weird drivers.
        health_percent = round((efull / edesign) * 100, 1) if edesign > 0 else 100.0

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