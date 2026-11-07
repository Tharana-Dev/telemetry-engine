#cli.py
from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.console import Group

import time
import platform
from engine.linux_sampler import LinuxCollector
from engine.psutil_sampler import PsutilCollector
from cli.dashboard import build_dashboard
from cli.data_collector import gather_snapshots


def main():
    console = Console()

    sys_type = platform.system()
    fallback_active = False
    fallback_reason = None
    degraded_subsystems: list[str] = []
    health: dict = {}

    if sys_type == "Linux":
        try:
            data = LinuxCollector()
        except Exception as e:
            data = PsutilCollector()
            fallback_active = True
            fallback_reason = type(e).__name__
        else:
            if hasattr(data, "get_system_health"):
                health = data.get_system_health()
                degraded_subsystems = [
                    name for name, err in health.items()
                    if err is not None
                ]
    else:
        data = PsutilCollector()

    # ---- Initial gather with a spinner splash ------------------------
    with console.status(
        "[bold cyan]Initializing... gathering first samples "
        "(this may take a moment)[/]",
        spinner="dots",
    ):
        snapshots = gather_snapshots(data)

    def compose() -> Group:
        table = build_dashboard(
            snapshots, sys_type, fallback_active, fallback_reason,
            degraded_subsystems, health,
        )
        footer = Text("\n Press Ctrl+C to exit.", style="bright_black")
        return Group(table, footer)

    initial = compose()

    try:
        with Live(
            initial,
            refresh_per_second=4,
            screen=True,               # alt-screen buffer, like htop
            transient=False,
        ) as live:
            while True:
                time.sleep(1)
                snapshots = gather_snapshots(data)   # ~1s
                live.update(compose())
    except KeyboardInterrupt:
        console.print("\nProgram interrupted. Exiting gracefully.")

if __name__ == "__main__":
    main()