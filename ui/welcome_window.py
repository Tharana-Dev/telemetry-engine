import ctypes
import os
import sys

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget

from identity_panel import IdentityPanel
from launchpad_panel import LaunchpadPanel
from personalization import personalization
from system_probe import GetData
from theme import StyleSheets


class WelcomeWindow(QMainWindow):
    launch_dashboard = Signal(object, str, bool)  # (SystemProfile, sector_id, skip_next_time)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Telemetry Mission Control")
        self.setMinimumSize(1100, 700)  # Was 900, 540
        self.setStyleSheet(StyleSheets.get_main_stylesheet())

        # 1. Collect system identity & WinTmp admin status
        self.profile = GetData().collect()

        # 2. Build the 2-column split layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        self.identity_panel = IdentityPanel(profile=self.profile, parent=self)
        self.launchpad_panel = LaunchpadPanel(profile=self.profile, parent=self)

        layout.addWidget(self.identity_panel, stretch=35)
        layout.addWidget(self.launchpad_panel, stretch=65)

        # 3. Connect Launchpad signals
        self.launchpad_panel.start_requested.connect(self._on_start)
        self.launchpad_panel.restart_admin_requested.connect(self._restart_as_admin)

        # 4. Accent picker → live repaint of every tinted surface
        personalization().accent_changed.connect(self._on_accent_changed)

    # ------------------------------------------------------------------ accent

    def _on_accent_changed(self) -> None:
        """Re-paints every accent-tinted surface after the user picks a swatch."""
        self.setStyleSheet(StyleSheets.get_main_stylesheet())
        self.identity_panel.refresh_accent()
        self.launchpad_panel.refresh_accent()

    # ------------------------------------------------------------------ launch

    def _on_start(self, sector_id: str, skip_next_time: bool) -> None:
        self.launch_dashboard.emit(self.profile, sector_id, skip_next_time)

    # ------------------------------------------------------------------ elevation

    def _restart_as_admin(self) -> None:
        """Relaunches the GUI without a console window using Windows UAC."""
        if sys.platform != "win32":
            return

        # Swap python.exe -> pythonw.exe so no black terminal window pops up
        executable = sys.executable
        if executable.lower().endswith("python.exe"):
            pythonw = executable[:-10] + "pythonw.exe"
            if os.path.exists(pythonw):
                executable = pythonw

        params = " ".join(f'"{arg}"' for arg in sys.argv)
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, None, 1
        )
        if result > 32:
            QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WelcomeWindow()

    # Temporary terminal logger to verify sector clicks
    window.launch_dashboard.connect(
        lambda profile, sector, skip: print(
            f"Opening sector '{sector}' on {profile.hostname} "
            f"(Admin: {profile.is_admin}, Skip next time: {skip})"
        )
    )

    window.show()
    sys.exit(app.exec())