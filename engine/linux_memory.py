from engine.models import MemorySnapshot


class LinuxMemorySampler:
    def __init__(self, mem_path: str = "/proc/meminfo"):
        self.memory_path = mem_path
        # Fatal health check: /proc/meminfo must be readable at construction.
        # FileNotFoundError / PermissionError bubble up to LinuxCollector.
        with open(self.memory_path, "r", encoding="utf-8") as f:
            f.readline()

    def get_snapshot(self) -> MemorySnapshot:
        mem = self.get_mem_data()

        mem_total = mem.get("MemTotal")
        mem_available = self._resolve_available(mem)

        total_gb = mem_total / (1024 * 1024) if mem_total is not None else None
        available_gb = mem_available / (1024 * 1024) if mem_available is not None else None

        # Derive used/percent only when both inputs are known AND total > 0.
        if total_gb is not None and available_gb is not None and total_gb > 0:
            used_gb = total_gb - available_gb
            used_pct = (1.0 - (available_gb / total_gb)) * 100
            return MemorySnapshot(
                total_gb=round(total_gb, 2),
                used_gb=round(used_gb, 2),
                used_pct=round(used_pct, 2),
                available_gb=round(available_gb, 2),
            )

        # Partial: one of the inputs is missing (or total == 0). Report the
        # figures we do have, None for everything that can't be derived.
        return MemorySnapshot(
            total_gb=round(total_gb, 2) if total_gb is not None else None,
            used_gb=None,
            used_pct=None,
            available_gb=round(available_gb, 2) if available_gb is not None else None,
        )

    @staticmethod
    def _resolve_available(mem: dict[str, int]) -> int | None:
        # MemAvailable is the authoritative figure on modern kernels.
        if "MemAvailable" in mem:
            return mem["MemAvailable"]
        # Fallback for pre-3.14 kernels / restricted containers. Only valid
        # if at least one component is actually present; otherwise the
        # answer is "unknown", not 0 (0 would read as 100% used).
        components = [k for k in ("MemFree", "Buffers", "Cached") if k in mem]
        if not components:
            return None
        return sum(mem[k] for k in components)

    def get_mem_data(self) -> dict[str, int]:
        mem_info: dict[str, int] = {}

        # Fatal: if /proc/meminfo disappears or becomes unreadable mid-run,
        # open() raises FileNotFoundError / PermissionError and we let it
        # bubble up to LinuxCollector.
        with open(self.memory_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

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