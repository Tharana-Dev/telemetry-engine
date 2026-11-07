import threading
import time
from collections import deque

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

class TelemetryWorker:
    def __init__(self, 
        collector,
        buffer: deque, 
        stop_event: threading.Event, 
        interval: float = 1.0
        ):
        self.collector = collector
        self.buffer = buffer
        self.stop_event = stop_event
        self.interval = interval
    
    def run(self):
        while not self.stop_event.is_set():
            snapshots = gather_snapshots(self.collector)
            self.buffer.append(snapshots)
            self.stop_event.wait(timeout=self.interval)
#Why? Because if you press Ctrl+C, time.sleep will wait the full 1 second before shutting down. stop_event.wait wakes up instantly when the stop event is set, making shutdown lightning fast
    