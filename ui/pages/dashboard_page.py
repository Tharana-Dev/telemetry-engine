from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QGridLayout, QWidget, QVBoxLayout

from ui.widgets.dashboard_card import DashboardCard
from ui.widgets.system_banner import SystemBanner 
from ui.data.dashboard_worker import DashboardDataCollector, DashboardSnapshot
from ui.system_probe import SystemProfile


class DashboardPage(QWidget):
    def __init__(self, profile: SystemProfile, parent=None):
        super().__init__(parent)

        self.cards = {}
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(0)
        
        # 1. The Grid at the TOP (No stretch above it)
        self.grid = QGridLayout()
        self.grid.setSpacing(20)
        self._grid() 
        main_layout.addLayout(self.grid)

        # 2. The Middle SPACE (This absorbs all the empty space)
        main_layout.addStretch(1)

        # 3. The Banner at the BOTTOM (No stretch below it)
        self.system_banner = SystemBanner(profile, self)
        main_layout.addWidget(self.system_banner)

        # --- Threading ---
        self.thread = QThread()
        self.worker = DashboardDataCollector()
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self.thread.quit)

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.poll_worker_data)

    def _grid(self):
        columns = 3 
        # Note: Changed to match the Hero layout + sub-rows
        card_configs = [
            ("CPU", ["Speed", "Board"]),
            ("Memory", ["Total", "Available"]),
            ("GPU", ["iGPU", "dGPU"]),
            ("Battery", ["Status", "Health", "Plugged In"]),
            ("Disk", ["Read", "Write"]),
            ("Network", ["Download", "Upload"]),
        ]

        for index, (title, rows) in enumerate(card_configs):
            row = index // columns
            col = index % columns

            card = DashboardCard(title=title, rows=rows)
            self.cards[title] = card
            self.grid.addWidget(card, row, col)

        for i in range(columns):
            self.grid.setColumnStretch(i, 1)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.thread.isRunning():
            self.worker._stop_event.clear()
            self.thread.start()
            self.ui_timer.start(1000)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.window().isMinimized():
            return
        self.ui_timer.stop()
        if hasattr(self, 'worker') and self.worker:
            self.worker._stop_event.set()
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def closeEvent(self, event: QCloseEvent):
        self.ui_timer.stop()
        if hasattr(self, 'worker') and self.worker:
            self.worker._stop_event.set()
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.wait(2000)
        super().closeEvent(event)

    def poll_worker_data(self):
        pending = self.worker.drain_pending_snapshots()
        if not pending:
            return
        self.update_ui(pending[-1])

    def update_ui(self, snapshot: DashboardSnapshot):
        # --- CPU CARD ---
        if "CPU" in self.cards:
            card = self.cards["CPU"]
            if snapshot.cpu_usage_pct is not None:
                color = "#ff4444" if snapshot.cpu_usage_pct > 80 else ("#ffbb33" if snapshot.cpu_usage_pct > 50 else None)
                # SET HERO
                card.set_hero(f"{snapshot.cpu_usage_pct:.1f}%", snapshot.cpu_usage_pct, color)
            if snapshot.cpu_freq_mhz is not None:
                card.update_row("Speed", f"{snapshot.cpu_freq_mhz / 1000:.2f} GHz")
            card.update_row("Board", snapshot.board_vendor if snapshot.board_vendor else "Admin Required", "#ffbb33" if not snapshot.board_vendor else None)

        # --- MEMORY CARD ---
        if "Memory" in self.cards:
            card = self.cards["Memory"]
            if snapshot.ram_used_gb is not None:
                # SET HERO
                card.set_hero(f"{snapshot.ram_used_gb:.1f} GB", snapshot.ram_used_pct)
            if snapshot.ram_total_gb is not None:
                card.update_row("Total", f"{snapshot.ram_total_gb:.1f} GB")
            if snapshot.ram_total_gb and snapshot.ram_used_gb:
                avail = snapshot.ram_total_gb - snapshot.ram_used_gb
                card.update_row("Available", f"{avail:.1f} GB")

        # --- GPU CARD ---
        if "GPU" in self.cards:
            card = self.cards["GPU"]
            gpu_label = "Active" if snapshot.dgpu_name else "Integrated"
            # SET HERO
            card.set_hero(gpu_label, None, "#00ff00" if snapshot.dgpu_name else None)
            
            if snapshot.igpu_name:
                card.update_row("iGPU", snapshot.igpu_name)
            else:
                card.update_row("iGPU", "Admin Required", "#ffbb33")

            if snapshot.dgpu_name:
                card.update_row("dGPU", snapshot.dgpu_name, "#00ff00")
            else:
                card.update_row("dGPU", "Not Detected")

        # --- BATTERY CARD ---
        if "Battery" in self.cards:
            card = self.cards["Battery"]
            if snapshot.battery_capacity is not None:
                color = "#ff4444" if snapshot.battery_capacity < 20 else None
                # SET HERO
                card.set_hero(f"{snapshot.battery_capacity}%", snapshot.battery_capacity, color)
                
            if snapshot.battery_status:
                card.update_row("Status", snapshot.battery_status)
            else:
                card.update_row("Status", "No Battery")

            if snapshot.battery_health is not None:
                health_color = "#ff4444" if snapshot.battery_health < 80 else None
                card.update_row("Health", f"{snapshot.battery_health:.0f}%", health_color)
            else:
                card.update_row("Health", "--")

            if snapshot.battery_online is not None:
                plugged_text = "Yes (AC)" if snapshot.battery_online else "No (Battery)"
                plugged_color = "#00ff00" if snapshot.battery_online else "#ffbb33"
                card.update_row("Plugged In", plugged_text, plugged_color)
            else:
                card.update_row("Plugged In", "--")

        # --- DISK CARD ---
        if "Disk" in self.cards:
            card = self.cards["Disk"]
            if snapshot.disk_space_free_gb is not None:
                # SET HERO
                card.set_hero(f"{snapshot.disk_space_free_gb:.1f} GB Free", snapshot.disk_space_used_pct)
            
            if snapshot.disk_read_bps is not None:
                card.update_row("Read", self._format_speed(snapshot.disk_read_bps))
            if snapshot.disk_write_bps is not None:
                card.update_row("Write", self._format_speed(snapshot.disk_write_bps))

        # --- NETWORK CARD ---
        if "Network" in self.cards:
            card = self.cards["Network"]
            if snapshot.net_download_bps and snapshot.net_download_bps > 0:
                down_mbps = snapshot.net_download_bps / 1_000_000
                # SET HERO
                card.set_hero(f"{down_mbps:.1f} Mbps")
            else:
                card.set_hero("Idle")
                
            if snapshot.net_download_bps is not None:
                card.update_row("Download", self._format_speed(snapshot.net_download_bps))
            if snapshot.net_upload_bps is not None:
                card.update_row("Upload", self._format_speed(snapshot.net_upload_bps))

    def _format_speed(self, bytes_per_sec: float | None) -> str:
        if bytes_per_sec is None or bytes_per_sec == 0:
            return "0 B/s"
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.0f} B/s"
        elif bytes_per_sec < 1024**2:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        elif bytes_per_sec < 1024**3:
            return f"{bytes_per_sec / (1024**2):.1f} MB/s"
        else:
            return f"{bytes_per_sec / (1024**3):.2f} GB/s"

    def refresh_theme(self):
        for card in self.cards.values():
            card.refresh_theme()
        self.system_banner.refresh_theme()