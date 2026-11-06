import os
import time
import platform
import textwrap
import shutil
from engine.linux_sampler import LinuxCollector
from engine.psutil_sampler import PsutilCollector


def _fmt(value, suffix="", fallback="N/A"):
    """Format a value with an optional suffix, defaulting to `fallback` when None."""
    return f"{value}{suffix}" if value is not None else fallback


def format_speed_bits(bytes_per_second):
    """Converts bytes/sec to bits/sec and formats as industry-standard Kbps or Mbps."""
    if bytes_per_second is None or bytes_per_second < 0:
        return "N/A"
    bits_per_second = bytes_per_second * 8
    kbps = bits_per_second / 1000

    if kbps < 1000:
        return f"{kbps:.2f} Kbps"
    else:
        mbps = kbps / 1000
        return f"{mbps:.2f} Mbps"


def format_total_data(total_bytes):
    """Converts total cumulative bytes into binary human-readable strings."""
    if total_bytes is None or total_bytes < 0:
        return "N/A"
    for unit in ['Bytes', 'KB', 'MB', 'GB', 'TB']:
        if total_bytes < 1024.0:
            return f"{total_bytes:.2f} {unit}"
        total_bytes /= 1024.0
    return f"{total_bytes:.2f} PB"


def format_disk_speed(bytes_per_second: float) -> str:
    """Formats a raw bytes/sec rate as a human-readable disk I/O speed.

    Uses binary base 1024 with KB/MB/GB labels — the `htop`/`ls -h`/`df -h`
    convention. Deliberately *different* from `format_speed_bits`, which uses
    networking's base-1000 bit convention (Kbps/Mbps).
    """
    if bytes_per_second is None or bytes_per_second < 0:
        return "N/A"
    if bytes_per_second < 1024:
        return f"{bytes_per_second:.1f} B/s"
    if bytes_per_second < 1024 ** 2:
        return f"{bytes_per_second / 1024:.2f} KB/s"
    if bytes_per_second < 1024 ** 3:
        return f"{bytes_per_second / 1024 ** 2:.2f} MB/s"
    return f"{bytes_per_second / 1024 ** 3:.2f} GB/s"


def format_disk_size(bytes_val: int | float | None) -> str:
    """Formats a raw byte count as a human-readable disk size (binary base 1024)."""
    if bytes_val is None or bytes_val < 0:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


def print_side_by_side(left_lines, right_lines):
    """Prints two lists of strings next to each other, dynamically sizing to the terminal."""
    term_width = shutil.get_terminal_size((100, 24)).columns

    if term_width < 80:
        term_width = 80

    avail_width = term_width - 7
    left_width = avail_width // 2
    right_width = avail_width - left_width

    wrapped_left = []
    for line in left_lines:
        if not line:
            wrapped_left.append("")
        else:
            wrapped_left.extend(textwrap.wrap(line, width=left_width, subsequent_indent='  '))

    wrapped_right = []
    for line in right_lines:
        if not line:
            wrapped_right.append("")
        else:
            wrapped_right.extend(textwrap.wrap(line, width=right_width, subsequent_indent='  '))

    max_lines = max(len(wrapped_left), len(wrapped_right))
    wrapped_left.extend([""] * (max_lines - len(wrapped_left)))
    wrapped_right.extend([""] * (max_lines - len(wrapped_right)))

    print(f"╔{'═' * (left_width + 2)}╤{'═' * (right_width + 2)}╗")
    for left, right in zip(wrapped_left, wrapped_right):
        print(f"║ {left:<{left_width}} │ {right:<{right_width}} ║")
    print(f"╚{'═' * (left_width + 2)}╧{'═' * (right_width + 2)}╝")


# =====================================================================
# DATA LAYER — samples the system. Never renders. Never raises.
# =====================================================================
def gather_snapshots(data) -> dict:
    """Call every sampler method once. Failures are captured, never raised.

    Returns a dict keyed by subsystem name. Each value is a tuple:
        (result, error_str)
    where `result` is whatever the sampler returned (snapshot object,
    None for no-hardware, or [] for first-tick), and `error_str` is None
    on success or str(exception) if the call raised.

    This is the ONLY place in main.py that touches `data`. Rendering
    happens strictly downstream of this function.
    """
    snapshots: dict = {}

    try: snapshots["cpu"] = (data.get_cpu_snapshot(), None)
    except Exception as e: snapshots["cpu"] = (None, str(e))

    try: snapshots["memory"] = (data.get_memory_snapshot(), None)
    except Exception as e: snapshots["memory"] = (None, str(e))

    try: snapshots["battery"] = (data.get_battery_snapshot(), None)
    except Exception as e: snapshots["battery"] = (None, str(e))

    try: snapshots["thermal"] = (data.get_thermal_snapshot(), None)
    except Exception as e: snapshots["thermal"] = (None, str(e))

    try: snapshots["disk_io"] = (data.get_disk_io_snapshot(), None)
    except Exception as e: snapshots["disk_io"] = (None, str(e))

    try: snapshots["disk_space"] = (data.get_disk_space_snapshot(), None)
    except Exception as e: snapshots["disk_space"] = (None, str(e))

    try: snapshots["network"] = (data.get_network_snapshot(), None)
    except Exception as e: snapshots["network"] = (None, str(e))

    return snapshots


# =====================================================================
# UI LAYER — pure rendering. Never touches `data`. Never crashes.
# =====================================================================
def build_dashboard(
    snapshots: dict,
    sys_type: str,
    fallback_active: bool,
    fallback_reason,
    degraded_subsystems: list[str],
    health: dict,
) -> tuple[list[str], list[str]]:
    """Render both dashboard columns from a pre-gathered snapshots dict.

    Pure function: no sampling, no I/O, no reference to the collector.
    Every datum shown comes from `snapshots`. Missing fields render as
    "N/A" via `_fmt` (or try/except for formatted numbers) — the dashboard
    never raises regardless of what the engine returned.
    """
    cpu, cpu_error = snapshots["cpu"]
    memory, memory_error = snapshots["memory"]
    battery, battery_error = snapshots["battery"]
    thermal, thermal_error = snapshots["thermal"]
    disk_io, disk_io_error = snapshots["disk_io"]
    disk_space, disk_space_error = snapshots["disk_space"]
    network_data, network_error = snapshots["network"]

    left_col: list[str] = []
    right_col: list[str] = []

    # ==========================================
    # LEFT COLUMN (System & Hardware)
    # ==========================================
    left_col.append("SYSTEM & HARDWARE")
    left_col.append("─────────────────────────────")

    if fallback_active:
        left_col.append(f"Engine Mode:  FALLBACK ({fallback_reason})")
    elif sys_type != "Linux":
        left_col.append(f"Engine Mode:  {sys_type} (psutil)")
    elif degraded_subsystems:
        left_col.append("Engine Mode:  Linux Native (degraded)")
        left_col.append(f"  Missing:    {', '.join(degraded_subsystems)}")
    else:
        left_col.append("Engine Mode:  Linux Native (/proc)")
    left_col.append("")

    # CPU & Memory
    left_col.append("CPU & MEMORY")
    if cpu is None:
        left_col.append("  CPU Usage:  Unavailable")
    else:
        left_col.append(f"  CPU Usage:  {_fmt(cpu.usage_pct, '%')}")

    if memory is None:
        left_col.append("  Memory:     Unavailable")
    else:
        mem_pct = _fmt(memory.used_pct, "%")
        try:
            mem_detail = f"{memory.used_gb:.2f} GB / {memory.total_gb:.2f} GB"
        except (TypeError, ValueError):
            mem_detail = "N/A"
        left_col.append(f"  Memory:     {mem_pct} ({mem_detail})")
    left_col.append("")

    # Battery
    left_col.append("BATTERY")
    if health.get("battery") is not None:
        # Init-time failure: sampler never constructed (PermissionError on
        # /sys/class/power_supply/, etc.)
        left_col.append("  Status:     Unavailable (Error)")
    elif battery_error is not None:
        # Mid-run failure: sampler constructed OK, but get_battery_snapshot()
        # raised on this tick.
        left_col.append("  Status:     Unavailable (Error)")
    elif battery is None:
        # No battery hardware at all (desktop, VM) — rule 3.
        left_col.append("  Status:     Not Detected (No Hardware)")
    else:
        left_col.append(f"  Status:     {_fmt(battery.status)}")
        cap_str = _fmt(battery.capacity, "%")
        try:
            health_str = f"{battery.health_percent:.1f}%"
        except (TypeError, ValueError):
            health_str = "N/A"
        left_col.append(f"  Capacity:   {cap_str}  (Health: {health_str})")

        try:
            draw_str = f"{battery.power_watts:.2f} W"
        except (TypeError, ValueError):
            draw_str = "N/A"

        if battery.status == "Discharging" and battery.hours_left is not None and battery.hours_left > 0:
            hrs = int(battery.hours_left)
            mins = int((battery.hours_left - hrs) * 60)
            time_str = f"{hrs}h {mins}m remaining"
        elif battery.status in ("Charging", "Full", "Not charging") or battery.online:
            time_str = "Wall Power (AC)"
        else:
            time_str = "N/A"

        left_col.append(f"  Power:      {draw_str}")
        left_col.append(f"  Time Est:   {time_str}")
    left_col.append("")

    # Thermal
    left_col.append("THERMAL & GPU")
    if thermal is None:
        left_col.append("  Status:     Unavailable")
    else:
        if thermal.sensor_available:
            cpu_t = _fmt(thermal.cpu_temp, "°C")
            cpu_m = _fmt(thermal.cpu_temp_max, "°C")
            left_col.append(f"  CPU Temp:   {cpu_t} (Max: {cpu_m})")

            if thermal.system_fans:
                for fan, rpm in thermal.system_fans.items():
                    left_col.append(f"  {fan.capitalize()}:{' ' * (10 - len(fan))} {rpm} RPM")
        else:
            left_col.append("  Sensor:     Unavailable")

        if thermal.gpu_available:
            if thermal.gpus:
                for gpu in thermal.gpus:
                    temp = _fmt(gpu.temperature_c, "°C")
                    util = _fmt(gpu.utilization_pct, "%")
                    watt = _fmt(gpu.power_w, "W")
                    left_col.append(f"  GPU [{_fmt(gpu.index)}]:     {_fmt(gpu.name)}")
                    left_col.append(f"    {temp} | {util} | {watt}")
            else:
                left_col.append("  GPU:        N/A")
        else:
            left_col.append("  GPU:        Not Detected")

    # ==========================================
    # RIGHT COLUMN (I/O & Network)
    # ==========================================
    right_col.append("I/O & NETWORK")
    right_col.append("─────────────────────────────")
    right_col.append("")

    # Disk Space
    right_col.append("DISK SPACE")
    if disk_space_error is not None:
        right_col.append(f"  Status:     Unavailable — {disk_space_error}")
    elif disk_space is not None:
        if disk_space.total_bytes is None:
            right_col.append("  Status:     Unavailable (read failed)")
        else:
            right_col.append(f"  Total:      {format_disk_size(disk_space.total_bytes)}")
            right_col.append(
                f"  Used:       {format_disk_size(disk_space.used_bytes)}  "
                f"({_fmt(disk_space.percent, '%')})"
            )
            right_col.append(f"  Free:       {format_disk_size(disk_space.free_bytes)}")
    right_col.append("")

    # Disk I/O
    right_col.append("DISK I/O")
    if disk_io_error is not None:
        right_col.append(f"  Status:     Unavailable — {disk_io_error}")
    elif disk_io is None:
        right_col.append("  Status:     Unavailable")
    elif disk_io == []:
        right_col.append("  Status:     Initializing (1s delta)")
    else:
        for io in disk_io:
            right_col.append(f"  {_fmt(io.device)}:")
            right_col.append(f"    Read:  {format_disk_speed(io.read_bps)}")
            right_col.append(f"    Write: {format_disk_speed(io.write_bps)}")
    right_col.append("")

    # Network
    right_col.append("NETWORK")
    if network_error is not None:
        right_col.append(f"  Status:     Unavailable — {network_error}")
    elif network_data is None:
        right_col.append("  Status:     Unavailable")
    elif network_data == []:
        right_col.append("  Status:     Initializing (1s delta)")
    else:
        for item in network_data:
            right_col.append(f"  {_fmt(item.interface)} ({_fmt(item.status)})")
            if item.status == "CONNECTED":
                down = format_speed_bits(item.download_bps)
                up = format_speed_bits(item.upload_bps)
                right_col.append(f"    ↓ {down} | ↑ {up}")
                right_col.append(
                    f"    Total Rx Err/Drop: {_fmt(item.rx_errors)} / {_fmt(item.rx_drops)}"
                )
                right_col.append(
                    f"    Total Tx Err/Drop: {_fmt(item.tx_errors)} / {_fmt(item.tx_drops)}"
                )
                right_col.append(f"    Total Data:  {format_total_data(item.total_bytes)}")
            elif item.status == "CONNECTING":
                right_col.append("    Initializing link...")
                right_col.append(f"    Total Data:  {format_total_data(item.total_bytes)}")
            else:
                right_col.append("    Offline / Unplugged")
            right_col.append("")

    return left_col, right_col


def main():
    sys_type = platform.system()
    fallback_active = False
    fallback_reason = None
    degraded_subsystems: list[str] = []
    health: dict = {}

    if sys_type == "Linux":
        try:
            data = LinuxCollector()
        except Exception as e:
            data = PsutilCollector()
            fallback_active = True
            fallback_reason = type(e).__name__
        else:
            if hasattr(data, "get_system_health"):
                health = data.get_system_health()
                degraded_subsystems = [
                    name for name, err in health.items()
                    if err is not None
                ]
    else:
        data = PsutilCollector()

    clear_command = 'cls' if sys_type == "Windows" else 'clear'

    # Splash: give the user visible feedback during the very first sample.
    # Without this, the terminal is blank for ~1s while the samplers
    # prime their baselines (disk/network first tick, `sensors -j` subprocess).
    os.system(clear_command)
    print("Initializing... gathering first samples (this may take a moment)")

    try:
        while True:
            snapshots = gather_snapshots(data)   # DATA — may take ~1s
            os.system(clear_command)             # UI — clear only after data ready
            left_col, right_col = build_dashboard(
                snapshots, sys_type, fallback_active, fallback_reason,
                degraded_subsystems, health,
            )                                     # UI — pure render
            print_side_by_side(left_col, right_col)
            print("\n Press Ctrl+C to exit.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully.")


if __name__ == "__main__":
    main()