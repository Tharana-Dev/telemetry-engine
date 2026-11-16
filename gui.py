import ctypes
import os
import sys
from ui.pages.notification_page import NotificationPage
from ui.data.notification_worker import NotificationWorker
from PySide6.QtCore import QThread

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QWidget, QStackedWidget
)

# UI Components
from ui.sidebar import Sidebar
from ui.identity_panel import IdentityPanel
from ui.launchpad_panel import LaunchpadPanel
from ui.personalization import personalization
from ui.system_probe import GetData
from ui.theme import StyleSheets

# Pages
from ui.pages.dashboard_page import DashboardPage
from ui.pages.cpu_page import CpuPage
from ui.pages.memory_page import MemoryPage
from ui.pages.gpu_page import GpuPage
from ui.pages.disk_page import DiskPage
from ui.pages.network_page import NetworkPage


class WelcomeWindow(QMainWindow):
    launch_dashboard = Signal(object, str, bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Telemetry Mission Control")
        self.setMinimumSize(1100, 700)
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

        # -- Home Page --
        home_widget = QWidget(self)
        home_layout = QHBoxLayout(home_widget)
        home_layout.setContentsMargins(32, 32, 32, 32)
        home_layout.setSpacing(32)

        self.identity_panel = IdentityPanel(profile=self.profile, parent=self)
        self.launchpad_panel = LaunchpadPanel(profile=self.profile, parent=self)

        home_layout.addWidget(self.identity_panel, stretch=35)
        home_layout.addWidget(self.launchpad_panel, stretch=65)

        self.page_indices["home"] = self.page_stack.addWidget(home_widget)

        # -- Telemetry Pages --
        self.dashboard_page = DashboardPage(self)
        self.page_indices["dashboard"] = self.page_stack.addWidget(self.dashboard_page)

        self.cpu_page = CpuPage(self)
        self.page_indices["cpu"] = self.page_stack.addWidget(self.cpu_page)

        self.memory_page = MemoryPage(self)
        self.page_indices["memory"] = self.page_stack.addWidget(self.memory_page)

        self.gpu_page = GpuPage(self)
        self.page_indices["gpu"] = self.page_stack.addWidget(self.gpu_page)

        self.disk_page = DiskPage(self)
        self.page_indices["disk"] = self.page_stack.addWidget(self.disk_page)

        self.network_page = NetworkPage(self)
        self.page_indices["network"] = self.page_stack.addWidget(self.network_page)

        self.notification_page = NotificationPage(self)
        self.page_indices["notifications"] = self.page_stack.addWidget(self.notification_page)

        # 3. Start the notification worker (runs for the whole app lifetime)
        self.notification_thread = QThread()
        self.notification_worker = NotificationWorker()
        self.notification_worker.moveToThread(self.notification_thread)

        self.notification_thread.started.connect(self.notification_worker.work)
        self.notification_worker.finished.connect(self.notification_thread.quit)

        self.notification_worker.notification_added.connect(self.notification_page.add_notification)
        self.notification_worker.notification_cleared.connect(self.notification_page.mark_resolved)

        self.notification_thread.start()

        # --- Connect Signals ---
        self.launchpad_panel.start_requested.connect(self.switch_page)
        self.launchpad_panel.restart_admin_requested.connect(self._restart_as_admin)

        # NEW THEME SIGNAL (was accent_changed)
        personalization().theme_changed.connect(self._on_theme_changed)

        # Set Default Page
        self.switch_page("home")

    def switch_page(self, page_id: str) -> None:
        if page_id in self.page_indices:
            self.page_stack.setCurrentIndex(self.page_indices[page_id])
            self.sidebar.set_active_page(page_id)

    def _on_theme_changed(self) -> None:
        """Called when the user clicks a theme swatch in the sidebar."""
        self.setStyleSheet(StyleSheets.get_main_stylesheet())

        self.sidebar.refresh_theme()
        self.identity_panel.refresh_theme()
        self.launchpad_panel.refresh_theme()

        self.dashboard_page.refresh_theme()
        self.cpu_page.refresh_theme()
        self.memory_page.refresh_theme()
        self.gpu_page.refresh_theme()
        self.disk_page.refresh_theme()
        self.network_page.refresh_theme()
        self.notification_page.refresh_theme()

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
        self.notification_worker._stop_event.set()
        self.notification_thread.quit()
        self.notification_thread.wait(2000)
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