from engine.models import (
    BatterySnapshot, CpuSnapshot, DiskIOSnapshot, MemorySnapshot, 
    NetworkSnapshot, ThermalSnapshot, DiskSpaceSnapshot
)
from engine.base_sampler import BaseSystemCollector
from engine.universal_impl.universal_disk import UniversalDiskSampler
from engine.universal_impl.universal_network import UniversalNetworkSampler
from engine.universal_impl.universal_thermal import UniversalThermalSampler
from engine.universal_impl.universal_memory import UniversalMemorySampler
from engine.universal_impl.universal_battery import UniversalBatterySampler
from engine.universal_impl.universal_cpu import UniversalCpuSampler
from engine.logger import logger
import time


class PsutilCollector(BaseSystemCollector):
    def __init__(self) -> None:
        # Mirroring LinuxCollector's architecture for init isolation.
        # A failed sampler here won't take down the whole dashboard.
        self.cpu_sampler: UniversalCpuSampler | None = None
        self.mem_sampler: UniversalMemorySampler | None = None
        self.battery_sampler: UniversalBatterySampler | None = None
        self.thermal_sampler: UniversalThermalSampler | None = None
        self.disk_sampler: UniversalDiskSampler | None = None
        self.network_sampler: UniversalNetworkSampler | None = None

        self._cpu_init_error: BaseException | None = None
        self._mem_init_error: BaseException | None = None
        self._battery_init_error: BaseException | None = None
        self._thermal_init_error: BaseException | None = None
        self._disk_init_error: BaseException | None = None
        self._network_init_error: BaseException | None = None

        self._runtime_errors: dict[str, BaseException] = {}
        self._last_logged_error = None
        self._last_log_time = 0

        try:
            self.cpu_sampler = UniversalCpuSampler()
        except Exception as e:
            self._cpu_init_error = e
            logger.error(f"Initialization failed for Universal CPU sampler: {e}")

        try:
            self.mem_sampler = UniversalMemorySampler()
        except Exception as e:
            self._mem_init_error = e
            logger.error(f"Initialization failed for Universal Memory sampler: {e}")

        try:
            self.battery_sampler = UniversalBatterySampler()
        except Exception as e:
            self._battery_init_error = e
            logger.error(f"Initialization failed for Universal Battery sampler: {e}")

        try:
            self.thermal_sampler = UniversalThermalSampler()
        except Exception as e:
            self._thermal_init_error = e
            logger.error(f"Initialization failed for Universal Thermal sampler: {e}")

        try:
            self.disk_sampler = UniversalDiskSampler()
        except Exception as e:
            self._disk_init_error = e
            logger.error(f"Initialization failed for Universal Disk sampler: {e}")

        try:
            self.network_sampler = UniversalNetworkSampler()
        except Exception as e:
            self._network_init_error = e
            logger.error(f"Initialization failed for Universal Network sampler: {e}")

    def _call(self, name, sampler, init_error, method_name):
        """K2: Centralized execution with log deduplication and runtime error tracking."""
        if sampler is None:
            return None
        try:
            result = getattr(sampler, method_name)()
            self._runtime_errors.pop(name, None)
            return result
        except Exception as e:
            error_msg = str(e)
            current_time = time.monotonic()
            is_duplicate = (error_msg == self._last_logged_error)
            is_recent = (current_time - self._last_log_time < 60)
            
            if not (is_duplicate and is_recent):
                logger.error(f"Runtime error in {name} sampler: {e}", exc_info=True)
                self._last_logged_error = error_msg
                self._last_log_time = current_time
                
            self._runtime_errors[name] = e
            return None

    def sampler_status(self) -> dict[str, BaseException | None]:
        return {
            "cpu": self._cpu_init_error,
            "memory": self._mem_init_error,
            "battery": self._battery_init_error,
            "thermal": self._thermal_init_error,
            "disk": self._disk_init_error,
            "network": self._network_init_error,
        }

    def get_system_health(self) -> dict[str, str | None]:
        health: dict[str, str | None] = {}
        status = self.sampler_status()
        for name in status:
            exc = self._runtime_errors.get(name) or status[name]
            health[name] = None if exc is None else str(exc)
        return health

    # =================================================================
    # DATA METHODS
    # =================================================================

    def get_cpu_snapshot(self):
        return self._call("cpu", self.cpu_sampler, self._cpu_init_error, "get_snapshot")

    def get_memory_snapshot(self) -> MemorySnapshot:
        return self._call("memory", self.mem_sampler, self._mem_init_error, "get_snapshot")

    def get_battery_snapshot(self) -> BatterySnapshot | None:
        return self._call("battery", self.battery_sampler, self._battery_init_error, "get_snapshot")

    def get_thermal_snapshot(self) -> ThermalSnapshot:
        return self._call("thermal", self.thermal_sampler, self._thermal_init_error, "get_thermal_snapshot")

    def get_disk_io_snapshot(self) -> list[DiskIOSnapshot]:
        return self._call("disk", self.disk_sampler, self._disk_init_error, "get_io_snapshot")

    def get_disk_space_snapshot(self) -> DiskSpaceSnapshot:
        return self._call("disk", self.disk_sampler, self._disk_init_error, "get_space_snapshot")

    def get_network_snapshot(self) -> list[NetworkSnapshot]:
        return self._call("network", self.network_sampler, self._network_init_error, "get_network_snapshot")