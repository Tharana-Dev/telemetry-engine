from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QGridLayout, QWidget, QVBoxLayout

from ui.widgets.dashboard_card import DashboardCard
from ui.data.dashboard_worker import DashboardDataCollector, DashboardSnapshot


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.cards = {}
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(0)
        
        self.grid = QGridLayout()
        self.grid.setSpacing(20)
        self._grid() 
        
        main_layout.addLayout(self.grid)
        
        # Notice: NO addStretch() here. We want the grid to fill the page.

        self.thread = QThread()
        self.worker = DashboardDataCollector()
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self.thread.quit)

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.poll_worker_data)

    def _grid(self):
        columns = 3 
        
        # We pass a hero_unit (e.g. "%" or "GB") and the sub-rows
        card_configs = [
            ("CPU", "%", ["Speed", "Board"]),
            ("Memory", "GB", ["Total", "Available"]),
            ("GPU", "", ["iGPU", "dGPU"]),
            ("Battery", "%", ["Status", "Health", "Plugged In"]),
            ("Disk", "GB Free", ["Read", "Write"]),
            ("Network", "Mbps", ["Download", "Upload", "Status"]),
        ]

        for index, (title, hero_unit, rows) in enumerate(card_configs):
            row = index // columns
            col = index % columns

            card = DashboardCard(title, hero_unit, rows)
            self.cards[title] = card
            self.grid.addWidget(card, row, col)

        # FORCE the grid to stretch and fill all available space
        for i in range(columns):
            self.grid.setColumnStretch(i, 1)
        for i in range(2): # 2 rows
            self.grid.setRowStretch(i, 1)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.thread.isRunning():
            self.worker._stop_event.clear()
            self.thread.start()
            self.ui_timer.start(1000)

    def hideEvent(self, event):
        super().hideEvent(event)
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
                card.set_hero(f"{snapshot.cpu_usage_pct:.1f} %", snapshot.cpu_usage_pct, color)
            if snapshot.cpu_freq_mhz:
                card.update_row("Speed", f"{snapshot.cpu_freq_mhz / 1000:.2f} GHz")
            card.update_row("Board", snapshot.board_vendor if snapshot.board_vendor else "Admin Required", "#ffbb33" if not snapshot.board_vendor else None)

        # --- MEMORY CARD ---
        if "Memory" in self.cards:
            card = self.cards["Memory"]
            if snapshot.ram_used_gb is not None:
                card.set_hero(f"{snapshot.ram_used_gb:.1f} GB", snapshot.ram_used_pct)
            if snapshot.ram_total_gb:
                card.update_row("Total", f"{snapshot.ram_total_gb:.1f} GB")
            if snapshot.ram_total_gb and snapshot.ram_used_gb:
                avail = snapshot.ram_total_gb - snapshot.ram_used_gb
                card.update_row("Available", f"{avail:.1f} GB")

        # --- GPU CARD ---
        if "GPU" in self.cards:
            card = self.cards["GPU"]
            gpu_name = snapshot.dgpu_name or snapshot.igpu_name or "Not Detected"
            card.set_hero(gpu_name, None, "#00ff00" if snapshot.dgpu_name else None)
            card.update_row("iGPU", snapshot.igpu_name if snapshot.igpu_name else "Admin Required")
            card.update_row("dGPU", snapshot.dgpu_name if snapshot.dgpu_name else "Not Detected")

        # --- BATTERY CARD ---
        if "Battery" in self.cards:
            card = self.cards["Battery"]
            if snapshot.battery_capacity is not None:
                color = "#ff4444" if snapshot.battery_capacity < 20 else None
                card.set_hero(f"{snapshot.battery_capacity} %", snapshot.battery_capacity, color)
            card.update_row("Status", snapshot.battery_status or "N/A")
            if snapshot.battery_health:
                card.update_row("Health", f"{snapshot.battery_health:.0f}%", "#ff4444" if snapshot.battery_health < 80 else None)
            if snapshot.battery_online is not None:
                card.update_row("Plugged In", "Yes (AC)" if snapshot.battery_online else "No (Battery)", "#00ff00" if snapshot.battery_online else "#ffbb33")

        # --- DISK CARD ---
        if "Disk" in self.cards:
            card = self.cards["Disk"]
            if snapshot.disk_space_free_gb is not None:
                card.set_hero(f"{snapshot.disk_space_free_gb:.1f} GB Free", snapshot.disk_space_used_pct)
            if snapshot.disk_read_bps is not None:
                card.update_row("Read", self._format_speed(snapshot.disk_read_bps))
            if snapshot.disk_write_bps is not None:
                card.update_row("Write", self._format_speed(snapshot.disk_write_bps))

        # --- NETWORK CARD ---
        if "Network" in self.cards:
            card = self.cards["Network"]
            # Network hero is Download speed in Mbps
            if snapshot.net_download_bps is not None:
                down_mbps = snapshot.net_download_bps / 1_000_000 # Assuming backend is in bytes, convert to Mbps
                card.set_hero(f"{down_mbps:.1f} Mbps", None, current_accent().primary)
                card.update_row("Download", self._format_speed(snapshot.net_download_bps))
            if snapshot.net_upload_bps is not None:
                card.update_row("Upload", self._format_speed(snapshot.net_upload_bps))
            card.update_row("Status", snapshot.net_status or "Offline")

    def _format_speed(self, bytes_per_sec: float | None) -> str:
        if not bytes_per_sec: return "0 B/s"
        if bytes_per_sec < 1024: return f"{bytes_per_sec:.0f} B/s"
        elif bytes_per_sec < 1024**2: return f"{bytes_per_sec / 1024:.1f} KB/s"
        elif bytes_per_sec < 1024**3: return f"{bytes_per_sec / (1024**2):.1f} MB/s"
        else: return f"{bytes_per_sec / (1024**3):.2f} GB/s"

    def refresh_accent(self):
        for card in self.cards.values():
            card.refresh_accent()