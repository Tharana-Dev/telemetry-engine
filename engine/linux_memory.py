from engine.models import MemorySnapshot


class LinuxMemorySampler:
    def __init__(self, mem_path: str = "/proc/meminfo"):
        self.memory_path = mem_path
        # Health check: fail fast if the file is unreadable at construction
        # time, rather than silently producing zeros on every snapshot.
        with open(self.memory_path, "r", encoding="utf-8") as f:
            f.readline()

    def get_snapshot(self) -> MemorySnapshot:
        mem = self.get_mem_data()

        mem_total = mem.get("MemTotal", 0)

        # M1: MemAvailable is missing on some older kernels (pre-3.14) and is
        # routinely hidden inside restricted containers. Treat *absent* as
        # "use the fallback", not as "0 bytes available" (which would read
        # as 100% used). A present-but-zero MemAvailable is a real reading
        # and must be preserved.
        mem_available = mem.get("MemAvailable")
        if mem_available is None:
            mem_available = (
                mem.get("MemFree", 0)
                + mem.get("Buffers", 0)
                + mem.get("Cached", 0)
            )

        if mem_total <= 0:
            return MemorySnapshot(
                total_gb=0.0,
                used_gb=0.0,
                used_pct=0.0,
                available_gb=0.0,
            )

        total = mem_total / (1024 * 1024)
        available = mem_available / (1024 * 1024)
        real_used_pct = (1.0 - (available / total)) * 100

        return MemorySnapshot(
            total_gb=round(total, 2),
            used_gb=round((total - available), 2),
            used_pct=round(real_used_pct, 2),
            available_gb=round(available, 2),
        )

    def get_mem_data(self) -> dict[str, int]:
        mem_info: dict[str, int] = {}

        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except IOError:
            # File unreadable / disappeared mid-run — nothing to parse.
            return {}

        for line in lines:
            parts = line.split(":", 1)
            if len(parts) < 2:
                continue
            key = parts[0].strip()
            value_parts = parts[1].split()
            if not value_parts:
                continue
            # M2: a single malformed line (e.g. "MemTotal: abc kB") must not
            # nuke the whole map. Skip it and keep parsing the rest.
            try:
                mem_info[key] = int(value_parts[0])
            except ValueError:
                continue

        return mem_info