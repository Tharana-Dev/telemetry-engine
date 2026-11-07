from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.console import Group

import time
import platform
import threading
from collections import deque

from cli.dashboard import build_dashboard
from cli.data_collector import TelemetryWorker, gather_snapshots


def main():
    console = Console()
    
    # ---- 1. Initialize Threading and Buffers -----------------------
    buffer = deque(maxlen=10)
    stop_event = threading.Event()
    
    sys_type = platform.system()
    fallback_active = False
    fallback_reason = None
    degraded_subsystems: list[str] = []
    health: dict = {}
    
    # ---- 2. Initialize the Correct Collector ----------------------
    if sys_type == "Linux":
        try:
            from engine.linux_sampler import LinuxCollector
            data = LinuxCollector()
        except Exception as e:
            data = PsutilCollector()
            fallback_active = True
            fallback_reason = type(e).__name__
    else:
        from engine.psutil_sampler import PsutilCollector
        data = PsutilCollector()
        
    if hasattr(data, "get_system_health"):
        health = data.get_system_health()
        degraded_subsystems = [
            name for name, err in health.items() if err is not None
        ]

    # ---- 3. Instantiate and Start the Background Worker ----------
    worker = TelemetryWorker(data, buffer, stop_event, interval=0.5)
    worker_thread = threading.Thread(target=worker.run, daemon=True)
    worker_thread.start()

    # ---- 4. UI Layout Definition ----------------------------------
    # Current active snapshot object used to paint the UI
    current_snapshots = None

    def compose() -> Group:
        # Falls back to an empty dictionary or initial structure if the thread hasn't caught up
        table = build_dashboard(
            current_snapshots, 
            sys_type, 
            fallback_active, 
            fallback_reason, 
            degraded_subsystems, 
            health
        )
        footer = Text("\n Press Ctrl+C to exit.", style="bright_black")
        return Group(table, footer)

    # ---- 5. Initial Gather for Splash Screen -----------------------
    with console.status(
        "[bold cyan]Initializing... gathering first samples (this may take a moment)[/]",
        spinner="dots",
    ):
        current_snapshots = gather_snapshots(data)
        initial_ui = compose()

    # ---- 6. Thread-Driven Live UI Loop ----------------------------
    try:
        with Live(
            initial_ui,
            refresh_per_second=4,
            screen=True,  # Alt-screen buffer mode (cleans terminal on exit)
            transient=False,
        ) as live:
            
            while not stop_event.is_set():
                time.sleep(1.0)  # UI Refresh rate tick
                
                # Drain the buffer to find the single most recent snapshot
                new_snapshot = None
                while True:
                    try:
                        new_snapshot = buffer.popleft()
                    except IndexError:
                        break  # Buffer completely drained
                
                # If the background thread has delivered updates, refresh UI
                if new_snapshot is not None:
                    current_snapshots = new_snapshot
                    live.update(compose())
                    
    # ---- 7. Graceful Shutdown -------------------------------------
    except KeyboardInterrupt:
        stop_event.set()
        worker_thread.join(timeout=2.0)  # Let worker cleanly stop polling
        console.print("\n[bold green]Shutdown cleanly.[/]")

if __name__ == "__main__":
    main()
