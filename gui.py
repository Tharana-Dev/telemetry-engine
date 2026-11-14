import ctypes
import os
import sys

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel
)

from ui.sidebar import Sidebar
from ui.identity_panel import IdentityPanel
from ui.launchpad_panel import LaunchpadPanel
from ui.personalization import personalization
from ui.system_probe import GetData
from ui.theme import StyleSheets, ThemeColors, ThemeFonts
from ui.pages.dashboard_page import DashboardPage

class PlaceholderPage(QWidget):
    """Temporary page for the sectors we haven't built yet."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon = QLabel("🚧", self)
        icon.setStyleSheet("font-size: 64px; margin-bottom: 16px;")
        
        lbl = QLabel(f"{title} Graphs Coming Soon", self)
        lbl.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: {ThemeFonts.SIZE_HERO}px; font-weight: 700;")
        
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(lbl)


class WelcomeWindow(QMainWindow):
    launch_dashboard = Signal(object, str, bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Telemetry Mission Control")
        self.setMinimumSize(1100, 900)
        self.setStyleSheet(StyleSheets.get_main_stylesheet())

        self.profile = GetData().collect()

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        self.sidebar = Sidebar(self)
        self.sidebar.page_requested.connect(self.switch_page)
        main_layout.addWidget(self.sidebar)

        # --- Page Stack ---
        self.page_stack = QStackedWidget(self)
        main_layout.addWidget(self.page_stack)

        self.page_indices = {}

        # -- Build Home Page --
        home_widget = QWidget(self)
        home_layout = QHBoxLayout(home_widget)
        home_layout.setContentsMargins(32, 32, 32, 32)
        home_layout.setSpacing(32)

        self.identity_panel = IdentityPanel(profile=self.profile, parent=self)
        self.launchpad_panel = LaunchpadPanel(profile=self.profile, parent=self)

        home_layout.addWidget(self.identity_panel, stretch=35)
        home_layout.addWidget(self.launchpad_panel, stretch=65)
        
        self.page_indices["home"] = self.page_stack.addWidget(home_widget)

        # Build the real dashboard page
        self.dashboard_page = DashboardPage(self)
        self.page_indices["dashboard"] = self.page_stack.addWidget(self.dashboard_page)

        # Build placeholders for the rest
        placeholder_ids = ["cpu", "memory", "gpu", "thermals", "disk", "network", "battery"]
        for page_id in placeholder_ids:
            placeholder = PlaceholderPage(page_id.upper(), self)
            self.page_indices[page_id] = self.page_stack.addWidget(placeholder)
        
        for page_id in placeholder_ids:
            # Make the title look nice (e.g., "dashboard" -> "DASHBOARD")
            placeholder = PlaceholderPage(page_id.upper(), self)
            self.page_indices[page_id] = self.page_stack.addWidget(placeholder)

        # 4. Connect Signals
        self.launchpad_panel.start_requested.connect(self.switch_page)
        self.launchpad_panel.restart_admin_requested.connect(self._restart_as_admin)
        personalization().accent_changed.connect(self._on_accent_changed)

        # 5. Set Default Page
        self.switch_page("home")

    def switch_page(self, page_id: str) -> None:
        if page_id in self.page_indices:
            self.page_stack.setCurrentIndex(self.page_indices[page_id])
            self.sidebar.set_active_page(page_id)

    def _on_accent_changed(self) -> None:
        self.setStyleSheet(StyleSheets.get_main_stylesheet())
        self.sidebar.refresh_accent()
        self.identity_panel.refresh_accent()
        self.launchpad_panel.refresh_accent()
        if hasattr(self, 'dashboard_page'):
            self.dashboard_page.refresh_accent()

    def _restart_as_admin(self) -> None:
        if sys.platform != "win32":
            return

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

    def closeEvent(self, event):
        """Safely shut down background threads before the window closes."""
        # Tell the dashboard to stop its timer and kill its thread
        if hasattr(self, 'dashboard_page'):
            self.dashboard_page.ui_timer.stop()
            if hasattr(self.dashboard_page, 'worker') and self.dashboard_page.worker:
                self.dashboard_page.worker._stop_event.set()
            if hasattr(self.dashboard_page, 'thread') and self.dashboard_page.thread.isRunning():
                self.dashboard_page.thread.wait(2000)
                
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WelcomeWindow()

    window.launch_dashboard.connect(
        lambda profile, sector, skip: print(
            f"Opening sector '{sector}' on {profile.hostname} "
            f"(Admin: {profile.is_admin}, Skip next time: {skip})"
        )
    )

    window.show()
    sys.exit(app.exec())