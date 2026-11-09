# cli/dashboard.py

from rich.console import Group
from rich.progress_bar import ProgressBar
from rich.style import Style
from rich.table import Table
from rich.text import Text

# Assuming these are in your formatters module now
from cli.formatters import (
    _fmt, 
    format_speed_bits, 
    format_total_data, 
    format_disk_speed, 
    format_disk_size
)

# =====================================================================
# UI LAYER — rich rendering. Never touches `data`. Never crashes.
# =====================================================================
def build_dashboard(
    snapshots: dict,
    sys_type: str,
    fallback_active: bool,
    fallback_reason,
    degraded_subsystems: list[str],
    health: dict,
    admin_mode: bool
) -> Group:
    """Render the two-column dashboard as a rich Group."""

    cpu, cpu_error = snapshots["cpu"]
    memory, memory_error = snapshots["memory"]
    battery, battery_error = snapshots["battery"]
    thermal, thermal_error = snapshots["thermal"]
    disk_io, disk_io_error = snapshots["disk_io"]
    disk_space, disk_space_error = snapshots["disk_space"]
    network_data, network_error = snapshots["network"]

    # ---- styles --------------------------------------------------------
    SECTION_STYLE = Style(color="cyan", bold=True)
    RULE_STYLE = Style(color="bright_black")
    ERROR_STYLE = Style(color="red", bold=True)
    DIM_STYLE = Style(color="bright_black")
    WARN_STYLE = Style(color="yellow")

    # ---- helpers -------------------------------------------------------
    def section(title: str) -> Text:
        return Text(title, style=SECTION_STYLE)

    def rule() -> Text:
        return Text("─" * 36, style=RULE_STYLE)  # Widened to match new table width

    def value_style(pct) -> str:
        """Returns the text color matching the progress bar."""
        if pct is None:
            return "bright_black"
        try:
            val = float(pct)
        except (TypeError, ValueError):
            return "bright_black"
        
        if val >= 85:
            return "red"
        if val >= 60:
            return "yellow"
        return "green"

    def bar(pct, width: int = 20) -> ProgressBar:
        """ProgressBar that pulses when unknown, and picks a threshold colour."""
        if pct is None:
            return ProgressBar(total=100, completed=50, width=width, pulse=True)
        
        try:
            val = max(0.0, min(100.0, float(pct)))
        except (TypeError, ValueError):
            return ProgressBar(total=100, completed=50, width=width, pulse=True)

        return ProgressBar(
            total=100,
            completed=val,
            width=width,
            complete_style=value_style(val),
        )

    def three_col_grid() -> Table:
        """label | bar | value"""
        g = Table.grid(padding=(0, 1))
        g.add_column(width=14)  # Fixed width for labels
        g.add_column(width=22)  # Bar slot
        g.add_column()          # Value
        return g

    def two_col_grid() -> Table:
        """label | value"""
        g = Table.grid(padding=(0, 1))
        g.add_column(width=18)  # Fixed width for labels (wider for network/disk)
        g.add_column()
        return g

    # =================================================================
    # LEFT COLUMN — System & Hardware
    # =================================================================
    left_items: list = []

    left_items.append(section("SYSTEM & HARDWARE"))
    left_items.append(rule())

    if fallback_active:
        left_items.append(Text(f"Engine Mode:  FALLBACK ({fallback_reason})", style=WARN_STYLE))
    elif sys_type != "Linux":
        left_items.append(Text(f"Engine Mode:  {sys_type} (psutil)"))
    elif degraded_subsystems:
        left_items.append(Text("Engine Mode:  Linux Native (degraded)", style=WARN_STYLE))
        left_items.append(Text(f"  Missing:    {', '.join(degraded_subsystems)}", style=WARN_STYLE))
    else:
        left_items.append(Text("Engine Mode:  Linux Native (/proc)"))
    left_items.append(Text(""))
    if sys_type == "Windows":
        admin_str = "Yes" if admin_mode else "No (CPU Temps Blocked)"
        left_items.append(Text(f"Admin Mode:  {admin_str}", style="green" if admin_mode else "yellow"))

    # --- CPU & Memory ------------------------------------------------
    cpu_mem = three_col_grid()

    if health.get("cpu") is not None or cpu_error is not None:
        cpu_mem.add_row(Text("CPU Usage:"), bar(None), Text("Unavailable (Error)", style=ERROR_STYLE))
    elif cpu is None:
        cpu_mem.add_row(Text("CPU Usage:"), bar(None), Text("Unavailable", style=DIM_STYLE))
    else:
        cpu_mem.add_row(
            Text("CPU Usage:"),
            bar(cpu.usage_pct),
            Text(_fmt(cpu.usage_pct, "%"), style=value_style(cpu.usage_pct)),
        )
        # --- NEW: Live Dynamic CPU Speed ---
        if getattr(cpu, "current_freq_mhz", None):
            cpu_mem.add_row(
                Text("CPU Speed:"),
                Text(""), # No bar
                Text(f"{cpu.current_freq_mhz / 1000:.2f} GHz")
            )

    if health.get("memory") is not None or memory_error is not None:
        cpu_mem.add_row(Text("Memory:"), bar(None), Text("Unavailable (Error)", style=ERROR_STYLE))
    elif memory is None:
        cpu_mem.add_row(Text("Memory:"), bar(None), Text("Unavailable", style=DIM_STYLE))
    else:
        try:
            detail = f"{memory.used_gb:.2f} GB / {memory.total_gb:.2f} GB"
        except (TypeError, ValueError):
            detail = "N/A"
        cpu_mem.add_row(
            Text("Memory:"),
            bar(memory.used_pct),
            Text(f"{_fmt(memory.used_pct, '%')} ({detail})", style=value_style(memory.used_pct)),
        )

    left_items.append(section("CPU & MEMORY"))
    left_items.append(cpu_mem)
    left_items.append(Text(""))

    # --- Battery -----------------------------------------------------
    bat = three_col_grid()

    if health.get("battery") is not None or battery_error is not None:
        bat.add_row(Text("Status:"), bar(None), Text("Unavailable (Error)", style=ERROR_STYLE))
    elif battery is None:
        bat.add_row(Text("Status:"), bar(None), Text("Not Detected (No Hardware)", style=DIM_STYLE))
    else:
        bat.add_row(Text("Status:"), Text(""), Text(_fmt(battery.status)))

        try:
            health_str = f"{battery.health_percent:.1f}%"
        except (TypeError, ValueError):
            health_str = "N/A"
        bat.add_row(
            Text("Capacity:"),
            bar(battery.capacity),
            Text(f"{_fmt(battery.capacity, '%')}  (Health: {health_str})", style=value_style(battery.capacity)),
        )

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

        bat.add_row(Text("Power:"), Text(""), Text(draw_str))
        bat.add_row(Text("Time Est:"), Text(""), Text(time_str))

    left_items.append(section("BATTERY"))
    left_items.append(bat)
    left_items.append(Text(""))

    # --- Thermal & GPU ----------------------------------------------
    th = two_col_grid()

    if health.get("thermal") is not None or thermal_error is not None:
        # Extract the actual error string
        err_msg = health.get("thermal") or thermal_error or "Unknown Error"
        th.add_row(Text("Status:"), Text(f"Unavailable ({err_msg})", style=ERROR_STYLE))
    elif thermal is None:
        th.add_row(Text("Status:"), Text("Unavailable", style=DIM_STYLE))
    else:
        # --- Hardware Info ---
        cpu_name = _fmt(getattr(thermal, "cpu_name", None))
        
        # --- NEW: Static Base Speed ---
        base_speed = ""
        if getattr(thermal, "cpu_base_speed_mhz", None):
            base_speed = f" ({thermal.cpu_base_speed_mhz / 1000:.1f} GHz Base)"
            
        th.add_row(Text("CPU:"), Text(f"{cpu_name}{base_speed}"))
        
        th.add_row(Text("Motherboard:"), Text(_fmt(getattr(thermal, "board_vendor", None))))
        
        if getattr(thermal, "igpu_name", None):
            th.add_row(Text("iGPU:"), Text(thermal.igpu_name))
            
        th.add_row(Text(""), Text(""))  # Blank line for visual separation
        
        # --- Temps ---
        if getattr(thermal, "sensor_available", False):
            if getattr(thermal, "cpu_temp", None) is not None:
                cpu_t = _fmt(thermal.cpu_temp, "°C")
                cpu_m = _fmt(getattr(thermal, "cpu_temp_max", None), "°C")
                th.add_row(Text("CPU Temp:"), Text(f"{cpu_t} (Max: {cpu_m})"))
            elif getattr(thermal, "sensor_error", None):
                # Use style="yellow" instead of [yellow] tags
                th.add_row(Text("CPU Temp:"), Text(thermal.sensor_error, style="yellow"))
            else:
                th.add_row(Text("CPU Temp:"), Text("N/A", style=DIM_STYLE))
            
            if getattr(thermal, "system_fans", None):
                for fan, rpm in thermal.system_fans.items():
                    th.add_row(Text(f"{fan.capitalize()}:"), Text(f"{rpm} RPM"))
        else:
            th.add_row(Text("Sensor:"), Text("Unavailable", style=DIM_STYLE))

        # --- GPU ---
        if getattr(thermal, "gpu_available", False):
            if getattr(thermal, "gpus", None):
                for gpu in thermal.gpus:
                    th.add_row(Text(f"GPU [{_fmt(gpu.index)}]:"), Text(_fmt(gpu.name)))
                    th.add_row(
                        Text(""),
                        Text(
                            f"{_fmt(gpu.temperature_c, '°C')} | "
                            f"{_fmt(gpu.utilization_pct, '%')} | "
                            f"{_fmt(gpu.power_w, 'W')}"
                        ),
                    )
            else:
                th.add_row(Text("GPU:"), Text("N/A", style=DIM_STYLE))
        else:
            th.add_row(Text("GPU:"), Text("Not Detected", style=DIM_STYLE))

    left_items.append(section("THERMAL & GPU"))
    left_items.append(th)
    left_items.append(Text(""))

    left_column = Group(*left_items)

    # =================================================================
    # RIGHT COLUMN — I/O & Network
    # =================================================================
    right_items: list = []

    right_items.append(section("I/O & NETWORK"))
    right_items.append(rule())
    right_items.append(Text(""))

    # --- Disk Space -------------------------------------------------
    ds = three_col_grid()

    if health.get("disk") is not None or disk_space_error is not None:
        ds.add_row(Text("Status:"), bar(None), Text("Unavailable (Error)", style=ERROR_STYLE))
    elif disk_space is None:
        ds.add_row(Text("Status:"), bar(None), Text("Unavailable", style=DIM_STYLE))
    elif disk_space.total_bytes is None:
        ds.add_row(Text("Status:"), bar(None), Text("Unavailable (read failed)", style=DIM_STYLE))
    else:
        ds.add_row(Text("Total:"), Text(""), Text(format_disk_size(disk_space.total_bytes)))
        ds.add_row(
            Text("Used:"),
            bar(disk_space.percent),
            Text(f"{_fmt(disk_space.percent, '%')}  ({format_disk_size(disk_space.used_bytes)})", style=value_style(disk_space.percent)),
        )
        ds.add_row(Text("Free:"), Text(""), Text(format_disk_size(disk_space.free_bytes)))

    right_items.append(section("DISK SPACE"))
    right_items.append(ds)
    right_items.append(Text(""))

    # --- Disk I/O ---------------------------------------------------
    dio = two_col_grid()

    if health.get("disk") is not None or disk_io_error is not None:
        dio.add_row(Text("Status:"), Text("Unavailable (Error)", style=ERROR_STYLE))
    elif disk_io is None:
        dio.add_row(Text("Status:"), Text("Unavailable", style=DIM_STYLE))
    elif disk_io == []:
        dio.add_row(Text("Status:"), Text("Initializing (1s delta)", style=WARN_STYLE))
    else:
        for io in disk_io:
            dio.add_row(Text(f"{_fmt(io.device)}:"), Text(""))
            dio.add_row(Text("Read:"), Text(format_disk_speed(io.read_bps)))
            dio.add_row(Text("Write:"), Text(format_disk_speed(io.write_bps)))

    right_items.append(section("DISK I/O"))
    right_items.append(dio)
    right_items.append(Text(""))

    # --- Network ----------------------------------------------------
    net = two_col_grid()

    if health.get("network") is not None or network_error is not None:
        net.add_row(Text("Status:"), Text("Unavailable (Error)", style=ERROR_STYLE))
    elif network_data is None:
        net.add_row(Text("Status:"), Text("Unavailable", style=DIM_STYLE))
    elif network_data == []:
        net.add_row(Text("Status:"), Text("Initializing (1s delta)", style=WARN_STYLE))
    else:
        for item in network_data:
            net.add_row(Text(f"{_fmt(item.interface)}:"), Text(_fmt(item.status)))
            if item.status == "CONNECTED":
                down = format_speed_bits(item.download_bps)
                up = format_speed_bits(item.upload_bps)
                net.add_row(Text("↓ / ↑:"), Text(f"{down} | {up}"))
                net.add_row(
                    Text("Rx Err/Drop:"),
                    Text(f"{_fmt(item.rx_errors)} / {_fmt(item.rx_drops)}"),
                )
                net.add_row(
                    Text("Tx Err/Drop:"),
                    Text(f"{_fmt(item.tx_errors)} / {_fmt(item.tx_drops)}"),
                )
                net.add_row(Text("Total Data:"), Text(format_total_data(item.total_bytes)))
            elif item.status == "CONNECTING":
                net.add_row(Text("Status:"), Text("Initializing link...", style=WARN_STYLE))
                net.add_row(Text("Total Data:"), Text(format_total_data(item.total_bytes)))
            else:
                net.add_row(Text("Status:"), Text("Offline / Unplugged", style=DIM_STYLE))
            net.add_row(Text(""), Text(""))

    right_items.append(section("NETWORK"))
    right_items.append(net)

    right_column = Group(*right_items)

    # =================================================================
    # OUTER TABLE & HEADER
    # =================================================================
    outer = Table.grid(padding=(0, 2), expand=True)
    outer.add_column(ratio=1, vertical="top")
    outer.add_column(ratio=1, vertical="top")
    outer.add_row(left_column, right_column)

    header = Text("SYSTEM TELEMETRY ENGINE", style="bold white on blue", justify="center")

    # Group everything together
    return Group(
        header,
        Text(""), # blank line
        outer
    )