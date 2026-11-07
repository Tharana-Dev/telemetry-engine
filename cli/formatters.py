#formatter.py

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
