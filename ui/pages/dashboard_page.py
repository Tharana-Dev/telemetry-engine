from PySide6.QtCore import QThread, QTimer, Qt
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

        # 4. Setup Worker Thread (Do not start it yet)
        self.thread = QThread()
        self.worker = DashboardDataCollector()
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self.thread.quit)

        # 5. Setup UI Timer (Do not start it yet)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.poll_worker_data)

    def _grid(self):
        columns = 3 

        card_configs = [
            ("CPU", ["Usage", "Speed"]),
            ("Memory", ["Used", "Total"]),
            ("GPU", ["iGPU", "dGPU"]),
            ("Battery", ["Capacity", "Status"]),
            ("Disk", ["Read", "Write", "Space"]),
            ("Network", ["Download", "Upload"]),
        ]

        for index, (title, rows) in enumerate(card_configs):
            row = index // columns
            col = index % columns

            card = StatCard(title=title, rows=rows)
            self.cards[title] = card
            self.grid.addWidget(card, row, col)

        # Make all columns stretch evenly to fill the width
        for i in range(columns):
            self.grid.setColumnStretch(i, 1)

    # ------------------------------------------------------------------
    # PAGE LIFECYCLE (Gather only when the page is visible)
    # ------------------------------------------------------------------

    def showEvent(self, event):
        """Fires when the user navigates to the Dashboard tab."""
        super().showEvent(event)
        if not self.thread.isRunning():
            print("DEBUG: Dashboard shown. Resuming data collection...")
            self.worker._stop_event.clear() # Reset the stop flag!
            self.thread.start()
            self.ui_timer.start(1000) # Update UI exactly once per second

    def hideEvent(self, event):
        """Fires when the user navigates away from the Dashboard tab."""
        super().hideEvent(event)
        print("DEBUG: Dashboard hidden. Pausing data collection...")
        self.ui_timer.stop()
        
        if hasattr(self, 'worker') and self.worker:
            self.worker._stop_event.set()
            
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait() # Wait for thread to safely exit

    def closeEvent(self, event: QCloseEvent):
        """Extra safety net if the app closes while Dashboard is active."""
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
        """Runs exactly every 1000ms. Drains the deque and aggregates the data."""
        pending = self.worker.drain_pending_snapshots()
        
        if not pending:
            return

        latest = pending[-1]

        # Calculate Average CPU to match Task Manager
        cpu_samples = [p.cpu_usage_pct for p in pending if p.cpu_usage_pct is not None]
        avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else None

        # Use max() for bursty things like Disk and Network
        max_ram_used = max((p.ram_used_gb for p in pending if p.ram_used_gb is not None), default=None)
        max_d_read = max((p.disk_read_bps for p in pending if p.disk_read_bps is not None), default=None)
        max_d_write = max((p.disk_write_bps for p in pending if p.disk_write_bps is not None), default=None)
        max_n_down = max((p.net_download_bps for p in pending if p.net_download_bps is not None), default=None)
        max_n_up = max((p.net_upload_bps for p in pending if p.net_upload_bps is not None), default=None)

        aggregated = DashboardSnapshot(
            cpu_name=latest.cpu_name,
            cpu_usage_pct=avg_cpu,
            cpu_freq_mhz=latest.cpu_freq_mhz,
            
            ram_total_gb=latest.ram_total_gb,
            ram_used_gb=max_ram_used,
            ram_used_pct=latest.ram_used_pct,
            
            igpu_name=latest.igpu_name,
            dgpu_name=latest.dgpu_name,
            
            battery_capacity=latest.battery_capacity,
            battery_status=latest.battery_status,
            
            disk_read_bps=max_d_read,
            disk_write_bps=max_d_write,
            disk_space_used_pct=latest.disk_space_used_pct,
            disk_space_free_gb=latest.disk_space_free_gb,
            
            net_status=latest.net_status,
            net_download_bps=max_n_down,
            net_upload_bps=max_n_up
        )

        self.update_ui(aggregated)

    def update_ui(self, snapshot: DashboardSnapshot):
        # --- CPU CARD ---
        if "CPU" in self.cards:
            card = self.cards["CPU"]
            if snapshot.cpu_usage_pct is not None:
                color = "#ff4444" if snapshot.cpu_usage_pct > 80 else ("#ffbb33" if snapshot.cpu_usage_pct > 50 else None)
                card.update_row("Usage", f"{snapshot.cpu_usage_pct:.1f}%", color)
            if snapshot.cpu_freq_mhz is not None:
                card.update_row("Speed", f"{snapshot.cpu_freq_mhz / 1000:.2f} GHz")

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
                card.set_row_visible("iGPU", False)

            if snapshot.dgpu_name:
                dgpu_display = snapshot.dgpu_name if len(snapshot.dgpu_name) < 25 else snapshot.dgpu_name[:22] + "..."
                card.update_row("dGPU", dgpu_display, "#00ff00")
                card.set_row_visible("dGPU", True)
            else:
                card.set_row_visible("dGPU", False)

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

    def _format_size(self, bytes_total: float | None) -> str:
        if bytes_total is None or bytes_total == 0:
            return "0 B"
        if bytes_total < 1024**2:
            return f"{bytes_total / 1024:.1f} KB"
        elif bytes_total < 1024**3:
            return f"{bytes_total / (1024**2):.1f} MB"
        else:
            return f"{bytes_total / (1024**3):.1f} GB"

    def refresh_accent(self):
        """Called when the user picks a new accent color from the sidebar."""
        for card in self.cards.values():
            card.refresh_accent()