from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QGridLayout, QWidget, QVBoxLayout

from ui.widgets.stat_card import StatCard
from ui.data.dashboard_worker import DashboardDataCollector, DashboardSnapshot


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.cards = {}
        
        # 1. Main wrapper layout (keeps the grid pinned to the top)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(0)
        
        # 2. Build the Grid
        self.grid = QGridLayout()
        self.grid.setSpacing(20)
        self._grid() 
        
        # 3. Add grid to layout, then add a stretch to push everything up
        main_layout.addLayout(self.grid)
        main_layout.addStretch()

        # 4. Setup Worker Thread
        self.thread = QThread()
        self.worker = DashboardDataCollector()
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self.thread.quit)

        # 5. Setup UI Timer
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.poll_worker_data)

    def _grid(self):
        columns = 3 

        card_configs = [
            ("CPU", ["Usage", "Speed", "Board"]),
            ("Memory", ["Used", "Total"]),
            ("GPU", ["iGPU", "dGPU"]),
            ("Battery", ["Capacity", "Status", "Health", "Plugged In"]),
            ("Disk", ["Read", "Write", "Space"]),
            ("Network", ["Download", "Upload"]),
        ]

        for index, (title, rows) in enumerate(card_configs):
            row = index // columns
            col = index % columns

            card = StatCard(title=title, rows=rows)
            self.cards[title] = card
            self.grid.addWidget(card, row, col)

        # Make all columns stretch evenly
        for i in range(columns):
            self.grid.setColumnStretch(i, 1)

    # ------------------------------------------------------------------
    # PAGE LIFECYCLE
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not self.thread.isRunning():
            self.worker._stop_event.clear()
            self.thread.start()
            self.ui_timer.start(1000)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.window().isMinimized():
            return  # Skip shutdown - the app was just minimized
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

    # ------------------------------------------------------------------
    # DATA HANDLING
    # ------------------------------------------------------------------

    def poll_worker_data(self):
        pending = self.worker.drain_pending_snapshots()
        if not pending:
            return

        latest = pending[-1]
        self.update_ui(latest)

    def update_ui(self, snapshot: DashboardSnapshot):
        # --- CPU CARD ---
        if "CPU" in self.cards:
            card = self.cards["CPU"]
            if snapshot.cpu_usage_pct is not None:
                color = "#ff4444" if snapshot.cpu_usage_pct > 80 else ("#ffbb33" if snapshot.cpu_usage_pct > 50 else None)
                card.update_row("Usage", f"{snapshot.cpu_usage_pct:.1f}%", color)
            if snapshot.cpu_freq_mhz is not None:
                card.update_row("Speed", f"{snapshot.cpu_freq_mhz / 1000:.2f} GHz")
            
            if snapshot.board_vendor:
                board = snapshot.board_vendor if len(snapshot.board_vendor) < 25 else snapshot.board_vendor[:22] + "..."
                card.update_row("Board", board)
            else:
                # Changed from "Unknown" to "Admin Required"
                card.update_row("Board", "Admin Required", "#ffbb33")
                

        # --- MEMORY CARD ---
        if "Memory" in self.cards:
            card = self.cards["Memory"]
            if snapshot.ram_used_gb is not None:
                card.update_row("Used", f"{snapshot.ram_used_gb:.1f} GB")
            if snapshot.ram_total_gb is not None:
                card.update_row("Total", f"{snapshot.ram_total_gb:.1f} GB")

        # --- GPU CARD ---
        if "GPU" in self.cards:
            card = self.cards["GPU"]
            
            if snapshot.igpu_name:
                igpu_display = snapshot.igpu_name if len(snapshot.igpu_name) < 25 else snapshot.igpu_name[:22] + "..."
                card.update_row("iGPU", igpu_display)
                card.set_row_visible("iGPU", True)
            else:
                card.update_row("iGPU", "Admin Required", "#ffbb33")
                card.set_row_visible("iGPU", True)

            if snapshot.dgpu_name:
                dgpu_display = snapshot.dgpu_name if len(snapshot.dgpu_name) < 25 else snapshot.dgpu_name[:22] + "..."
                card.update_row("dGPU", dgpu_display, "#00ff00")
                card.set_row_visible("dGPU", True)
            else:
                card.update_row("dGPU", "Not Detected")
                card.set_row_visible("dGPU", True)

        # --- BATTERY CARD ---
        if "Battery" in self.cards:
            card = self.cards["Battery"]
            
            if snapshot.battery_capacity is not None:
                color = "#ff4444" if snapshot.battery_capacity < 20 else None
                card.update_row("Capacity", f"{snapshot.battery_capacity}%", color)
            else:
                card.update_row("Capacity", "N/A")
                
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
            if snapshot.disk_read_bps is not None:
                card.update_row("Read", self._format_speed(snapshot.disk_read_bps))
            if snapshot.disk_write_bps is not None:
                card.update_row("Write", self._format_speed(snapshot.disk_write_bps))
            
            if snapshot.disk_space_free_gb is not None:
                if snapshot.disk_space_free_gb < 1.0:
                    card.update_row("Space", f"{snapshot.disk_space_free_gb * 1024:.0f} MB Free")
                else:
                    card.update_row("Space", f"{snapshot.disk_space_free_gb:.1f} GB Free")

        # --- NETWORK CARD ---
        if "Network" in self.cards:
            card = self.cards["Network"]
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

    def refresh_accent(self):
        for card in self.cards.values():
            card.refresh_accent()