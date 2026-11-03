from engine.base_sampler import BaseSystemCollector
from engine.linux_memory import LinuxMemorySampler
from engine.linux_cpu import LinuxCpuSampler
from engine.linux_battery import LinuxBatterySampler
from engine.linux_thermal import LinuxThermalSampler
from engine.linux_disk import LinuxDiskSampler
from engine.linux_network import LinuxNetworkSampler
from engine.models import NetworkSnapshot  # re-exported for callers


class SamplerUnavailableError(RuntimeError):
    """The named sampler failed to initialize and therefore cannot be used.

    Raised by ``LinuxCollector.get_*()`` when the underlying sampler was
    never constructed (e.g. sysfs permission denied at construction time).
    The original exception is preserved in ``.original`` so callers can
    inspect or re-raise it if needed.
    """

    def __init__(self, name: str, original: BaseException | None) -> None:
        detail = f"{type(original).__name__}: {original}" if original else "unknown"
        super().__init__(f"{name} sampler unavailable ({detail})")
        self.name = name
        self.original = original


class SamplerRuntimeError(RuntimeError):
    """The named sampler was constructed, but its ``get_*()`` call failed.

    Wraps the original exception so callers see a single actionable message
    in ``str(e)`` while still being able to unwrap via ``.original`` or
    ``__cause__``.
    """

    def __init__(self, name: str, original: BaseException) -> None:
        super().__init__(f"{name} sampler error ({type(original).__name__}: {original})")
        self.name = name
        self.original = original


class LinuxCollector(BaseSystemCollector):
    def __init__(self) -> None:
        # K1: each sampler is constructed in isolation. Previously a single
        # PermissionError from e.g. LinuxBatterySampler's sysfs scan would
        # abort the entire collector, forcing main.py into psutil fallback
        # and throwing away every other native /proc metric. Now each
        # failure is recorded and only surfaces when its own get_*() is
        # called — main.py can still serve CPU/Mem/Disk/Net natively while
        # reporting "battery unavailable".
        self.cpu_sampler: LinuxCpuSampler | None = None
        self.mem_sampler: LinuxMemorySampler | None = None
        self.battery_sampler: LinuxBatterySampler | None = None
        self.thermal_sampler: LinuxThermalSampler | None = None
        self.disk_sampler: LinuxDiskSampler | None = None
        self.network_sampler: LinuxNetworkSampler | None = None

        self._cpu_init_error: BaseException | None = None
        self._mem_init_error: BaseException | None = None
        self._battery_init_error: BaseException | None = None
        self._thermal_init_error: BaseException | None = None
        self._disk_init_error: BaseException | None = None
        self._network_init_error: BaseException | None = None

        try:
            self.cpu_sampler = LinuxCpuSampler()
        except Exception as e:
            self._cpu_init_error = e

        try:
            self.mem_sampler = LinuxMemorySampler()
        except Exception as e:
            self._mem_init_error = e

        try:
            self.battery_sampler = LinuxBatterySampler()
        except Exception as e:
            self._battery_init_error = e

        try:
            self.thermal_sampler = LinuxThermalSampler()
        except Exception as e:
            self._thermal_init_error = e

        try:
            self.disk_sampler = LinuxDiskSampler()
        except Exception as e:
            self._disk_init_error = e

        try:
            self.network_sampler = LinuxNetworkSampler()
        except Exception as e:
            self._network_init_error = e

    def _call(self, name, sampler, init_error, method_name):
        """K2: every failure mode becomes a single, self-describing exception.

        - Sampler never constructed  -> SamplerUnavailableError
        - Sampler raised mid-call    -> SamplerRuntimeError (chains original)
        """
        if sampler is None:
            raise SamplerUnavailableError(name, init_error)
        try:
            return getattr(sampler, method_name)()
        except Exception as e:
            raise SamplerRuntimeError(name, e) from e
    
    def sampler_status(self) -> dict[str, BaseException | None]:
        """Per-sampler init status: None = healthy, exception = failed.

        Used by the UI to distinguish "running natively" from "running natively
        but with some subsystems broken" (partial failure via K1).
        """
        return {
            "cpu": self._cpu_init_error,
            "memory": self._mem_init_error,
            "battery": self._battery_init_error,
            "thermal": self._thermal_init_error,
            "disk": self._disk_init_error,
            "network": self._network_init_error,
        }
        
    def get_cpu_snapshot(self):
        return self._call("cpu", self.cpu_sampler, self._cpu_init_error, "get_snapshot")

    def get_memory_snapshot(self):
        return self._call("memory", self.mem_sampler, self._mem_init_error, "get_snapshot")

    def get_battery_snapshot(self):
        return self._call("battery", self.battery_sampler, self._battery_init_error,
                          "get_battery_snapshot")

    def get_thermal_snapshot(self):
        return self._call("thermal", self.thermal_sampler, self._thermal_init_error,
                          "get_thermal_snapshot")

    def get_disk_io_snapshot(self):
        return self._call("disk", self.disk_sampler, self._disk_init_error, "get_io_snapshot")

    def get_disk_space_snapshot(self):
        return self._call("disk", self.disk_sampler, self._disk_init_error, "get_space_snapshot")

    def get_network_snapshot(self):
        return self._call("network", self.network_sampler, self._network_init_error,
                          "get_network_snapshot")