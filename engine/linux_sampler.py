from engine.base_sampler import BaseSystemCollector
from engine.linux_memory import LinuxMemorySampler
from engine.linux_cpu import LinuxCpuSampler
from engine.linux_battery import LinuxBatterySampler
from engine.linux_thermal import LinuxThermalSampler
from engine.linux_disk import LinuxDiskSampler
from engine.linux_network import LinuxNetworkSampler
from engine.logger import logger
import time

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
        
        self._runtime_errors: dict[str, BaseException] = {}
        self._last_logged_error = None
        self._last_log_time = 0

        try:
            self.cpu_sampler = LinuxCpuSampler()
        except Exception as e:
            self._cpu_init_error = e
            logger.error(f"Initialization failed for CPU sampler: {e}")

        try:
            self.mem_sampler = LinuxMemorySampler()
        except Exception as e:
            self._mem_init_error = e
            logger.error(f"Initialization failed for Memory sampler: {e}")

        try:
            self.battery_sampler = LinuxBatterySampler()
        except Exception as e:
            self._battery_init_error = e
            logger.error(f"Initialization failed for Battery sampler: {e}")

        try:
            self.thermal_sampler = LinuxThermalSampler()
        except Exception as e:
            self._thermal_init_error = e
            logger.error(f"Initialization failed for Thermal sampler: {e}")

        try:
            self.disk_sampler = LinuxDiskSampler()
        except Exception as e:
            self._disk_init_error = e
            logger.error(f"Initialization failed for Disk sampler: {e}")

        try:
            self.network_sampler = LinuxNetworkSampler()
        except Exception as e:
            self._network_init_error = e
            logger.error(f"Initialization failed for Network sampler: {e}")

    def _call(self, name, sampler, init_error, method_name):
        if sampler is None:
           return None
        try:
            result =  getattr(sampler, method_name)()
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
    
    def get_system_health(self) -> dict[str, str | None]:
        health: dict[str, str | None] = {}
        status = self.sampler_status()
        for name in status:
            exc = self._runtime_errors.get(name) or status[name]
            health[name] = None if exc is None else str(exc)
        return health