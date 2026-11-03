import os
import time
import platform
import textwrap
import shutil
from engine.linux_sampler import LinuxCollector
from engine.psutil_sampler import PsutilCollector


def format_speed_bits(bytes_per_second):
    """Converts bytes/sec to bits/sec and formats as industry-standard Kbps or Mbps."""
    bits_per_second = bytes_per_second * 8
    kbps = bits_per_second / 1000

    if kbps < 1000:
        return f"{kbps:.2f} Kbps"
    else:
        mbps = kbps / 1000
        return f"{mbps:.2f} Mbps"


def format_total_data(total_bytes):
    """Converts total cumulative bytes into binary human-readable strings."""
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
    """Formats a raw byte count as a human-readable disk size (binary base 1024).

    This is `format_total_data` with a shorter label set ("B" instead of
    "Bytes") so it reads well next to the Disk Space rows. Kept as a distinct
    helper because the disk-space UI will never reach the PB range and the
    label width matters more here than in the network totals.
    """
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


def _sampler_state(data, kind: str):
    """Read (is_ready, has_known_devices, last_error) from the sampler.

    Falls back to (True, True, None) so this works transparently with
    PsutilCollector (which has no raw samplers) or older sampler versions
    that don't yet expose the state properties.
    """
    sampler = getattr(data, f"{kind}_sampler", None)
    if sampler is None or not hasattr(sampler, "is_ready"):
        return (True, True, None)
    return (sampler.is_ready, sampler.has_known_devices, sampler.last_error)


def main():
    sys_type = platform.system()
    fallback_active = False
    fallback_reason = None
    degraded_subsystems: list[str] = []

    if sys_type == "Linux":
        try:
            data = LinuxCollector()
        except Exception as e:
            data = PsutilCollector()
            fallback_active = True
            fallback_reason = type(e).__name__
        else:
            if hasattr(data, "sampler_status"):
                degraded_subsystems = [
                    name for name, err in data.sampler_status().items()
                    if err is not None
                ]
    else:
        data = PsutilCollector()

    clear_command = 'cls' if sys_type == "Windows" else 'clear'

    try:
        while True:
            try: cpu, cpu_error = data.get_cpu_snapshot(), None
            except Exception as e: cpu, cpu_error = None, str(e)

            try: memory, memory_error = data.get_memory_snapshot(), None
            except Exception as e: memory, memory_error = None, str(e)

            try: battery, battery_error = data.get_battery_snapshot(), None
            except Exception as e: battery, battery_error = None, str(e)

            try: thermal, thermal_error = data.get_thermal_snapshot(), None
            except Exception as e: thermal, thermal_error = None, str(e)

            try: disk_io, disk_io_error = data.get_disk_io_snapshot(), None
            except Exception as e: disk_io, disk_io_error = None, str(e)

            try: disk_space, disk_space_error = data.get_disk_space_snapshot(), None
            except Exception as e: disk_space, disk_space_error = None, str(e)

            try: network_data, network_error = data.get_network_snapshot(), None
            except Exception as e: network_data, network_error = None, str(e)

            os.system(clear_command)

            left_col = []
            right_col = []

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
                left_col.append(f"  CPU Usage:  {cpu.usage_pct}%")

            if memory is None:
                left_col.append("  Memory:     Unavailable")
            else:
                left_col.append(f"  Memory:     {memory.used_pct}% ({memory.used_gb:.2f} GB / {memory.total_gb:.2f} GB)")
            left_col.append("")

            # Battery
            left_col.append("BATTERY")
            if battery_error is not None:
                left_col.append("  Status:     Unavailable")
            elif battery is None:
                left_col.append("  Status:     Not Detected")
            else:
                left_col.append(f"  Status:     {battery.status}")
                cap_str = f"{battery.capacity}%" if battery.capacity is not None else "N/A"
                health_str = f"{battery.health_percent:.1f}%" if battery.health_percent is not None else "N/A"
                left_col.append(f"  Capacity:   {cap_str}  (Health: {health_str})")

                draw_str = f"{battery.power_watts:.2f} W" if battery.power_watts is not None else "N/A"
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
                    cpu_t = f"{thermal.cpu_temp}°C" if thermal.cpu_temp is not None else "N/A"
                    cpu_m = f"{thermal.cpu_temp_max}°C" if thermal.cpu_temp_max is not None else "N/A"
                    left_col.append(f"  CPU Temp:   {cpu_t} (Max: {cpu_m})")

                    if thermal.system_fans:
                        for fan, rpm in thermal.system_fans.items():
                            left_col.append(f"  {fan.capitalize()}:{' ' * (10 - len(fan))} {rpm} RPM")
                else:
                    left_col.append(f"  Sensor:     {thermal.sensor_error}")

                if thermal.gpu_available:
                    if thermal.gpus:
                        for gpu in thermal.gpus:
                            temp = f"{gpu.temperature_c}°C" if gpu.temperature_c is not None else "N/A"
                            util = f"{gpu.utilization_pct}%" if gpu.utilization_pct is not None else "N/A"
                            watt = f"{gpu.power_w}W" if gpu.power_w is not None else "N/A"
                            left_col.append(f"  GPU [{gpu.index}]:     {gpu.name}")
                            left_col.append(f"    {temp} | {util} | {watt}")
                    else:
                        left_col.append("  GPU:        N/A")
                else:
                    err = thermal.gpu_error or "Unavailable"
                    left_col.append(f"  GPU:        {err}")

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
                    right_col.append(f"  Used:       {format_disk_size(disk_space.used_bytes)}  ({disk_space.percent}%)")
                    right_col.append(f"  Free:       {format_disk_size(disk_space.free_bytes)}")
            right_col.append("")

            # Disk I/O
            right_col.append("DISK I/O")
            if disk_io_error is not None:
                right_col.append(f"  Status:     Unavailable — {disk_io_error}")
            elif disk_io is not None:
                is_ready, has_devices, last_err = _sampler_state(data, "disk")
                if last_err is not None:
                    right_col.append(f"  Status:     Unavailable ({last_err.value})")
                elif not is_ready:
                    right_col.append("  Status:     Initializing (1s delta)")
                elif not has_devices:
                    right_col.append("  Status:     No physical devices detected")
                elif not disk_io:
                    right_col.append("  Status:     Idle")
                else:
                    for io in disk_io:
                        right_col.append(f"  {io.device}:")
                        right_col.append(f"    Read:  {format_disk_speed(io.read_bps)}")
                        right_col.append(f"    Write: {format_disk_speed(io.write_bps)}")
            right_col.append("")
            
            # Network
            right_col.append("NETWORK")
            if network_error is not None:
                right_col.append(f"  Status:     Unavailable — {network_error}")
            elif network_data is not None:
                is_ready, has_devices, last_err = _sampler_state(data, "network")
                if last_err is not None:
                    right_col.append(f"  Status:     Unavailable ({last_err.value})")
                elif not is_ready:
                    right_col.append("  Status:     Initializing (1s delta)")
                elif not has_devices:
                    right_col.append("  Status:     No interfaces detected")
                elif not network_data:
                    right_col.append("  Status:     Idle")
                else:
                    for item in network_data:
                        right_col.append(f"  {item.interface} ({item.status})")
                        if item.status == "CONNECTED":
                            down = format_speed_bits(item.download_bps)
                            up = format_speed_bits(item.upload_bps)
                            right_col.append(f"    ↓ {down} | ↑ {up}")
                            right_col.append(f"    Total Rx Err/Drop: {item.rx_errors} / {item.rx_drops}")
                            right_col.append(f"    Total Tx Err/Drop: {item.tx_errors} / {item.tx_drops}")
                            right_col.append(f"    Total Data:  {format_total_data(item.total_bytes)}")
                        elif item.status == "CONNECTING":
                            right_col.append("    Initializing link...")
                            right_col.append(f"    Total Data:  {format_total_data(item.total_bytes)}")
                        else:
                            right_col.append("    Offline / Unplugged")
                        right_col.append("")

            # ==========================================
            # PRINT EVERYTHING
            # ==========================================
            print_side_by_side(left_col, right_col)

            print("\n Press Ctrl+C to exit.")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully.")


if __name__ == "__main__":
    main()