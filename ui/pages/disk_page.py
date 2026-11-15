from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ui.data.disk_worker import DiskWorker, DiskWorkerSnapshot
from ui.widgets.stat_card import StatCard
from ui.widgets.live_graph import LiveGraph

class DiskPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(32, 32, 32, 32)
        self._layout.setSpacing(20)

        # 1. Graphs
        self._graph_layout = QHBoxLayout()
        self._graph_layout.setSpacing(20)

        self._read_graph = LiveGraph("Disk Read Speed", "Speed (MB/s)", (0, 10))
        self._write_graph = LiveGraph("Disk Write Speed", "Speed (MB/s)", (0, 10))

        self._graph_layout.addWidget(self._read_graph)
        self._graph_layout.addWidget(self._write_graph)

        # 2. Stat Cards
        self._stats_layout = QHBoxLayout()
        self._stats_layout.setSpacing(20)
        
        self._space_card = StatCard("Storage Space", ["Device", "Total", "Used", "Free"])
        self._io_card = StatCard("Live I/O", ["Read", "Write", "Usage %"])

        self._stats_layout.addWidget(self._space_card)
        self._stats_layout.addWidget(self._io_card)

        self._layout.addLayout(self._graph_layout, stretch=3)
        self._layout.addLayout(self._stats_layout, stretch=2)

        # 3. Data & Threading
        self._read_data = []
        self._write_data = []
        self._latest_snapshot = None

        self.thread = QThread()
        self.worker = DiskWorker()
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self.thread.quit)
        
        # Dual Timers
        self.graph_timer = QTimer()
        self.graph_timer.timeout.connect(self.update_graphs)
        
        self.card_timer = QTimer()
        self.card_timer.timeout.connect(self.update_cards)

    def update_graphs(self):
        pending = self.worker.drain_pending_snapshots()
        if not pending:
            return

        self._latest_snapshot = pending[-1]

        for snapshot in pending:
            # Convert Bytes to MB for the graph
            read_mb = (snapshot.read_bps / (1024**2)) if snapshot.read_bps else 0.0
            write_mb = (snapshot.write_bps / (1024**2)) if snapshot.write_bps else 0.0
            
            self._read_data.append(read_mb)
            self._write_data.append(write_mb)

        self._read_data = self._read_data[-600:]
        self._write_data = self._write_data[-600:]

        # Dynamic Y-Axis
        max_read = max(self._read_data) if self._read_data else 0.0
        max_write = max(self._write_data) if self._write_data else 0.0

        self._read_graph.setYRange(0, max(10.0, max_read * 1.2), padding=0)
        self._write_graph.setYRange(0, max(10.0, max_write * 1.2), padding=0)

        self._read_graph.set_data(self._read_data)
        self._write_graph.set_data(self._write_data)

    def update_cards(self):
        if not self._latest_snapshot:
            return
            
        snap = self._latest_snapshot

        # --- Space Card ---
        self._space_card.update_row("Device", snap.device if snap.device else "C:\\")
        
        if snap.total_bytes:
            self._space_card.update_row("Total", f"{snap.total_bytes / (1024**3):.1f} GB")
        if snap.used_bytes:
            self._space_card.update_row("Used", f"{snap.used_bytes / (1024**3):.1f} GB")
        if snap.free_bytes:
            self._space_card.update_row("Free", f"{snap.free_bytes / (1024**3):.1f} GB")

        # --- I/O Card ---
        self._io_card.update_row("Read", self._format_speed(snap.read_bps))
        self._io_card.update_row("Write", self._format_speed(snap.write_bps))
        
        if snap.percent is not None:
            color = "#ff4444" if snap.percent > 90 else None
            self._io_card.update_row("Usage %", f"{snap.percent:.1f}%", color)

    def _format_speed(self, bytes_per_sec: float | None) -> str:
        if not bytes_per_sec: return "0 B/s"
        if bytes_per_sec < 1024: return f"{bytes_per_sec:.0f} B/s"
        elif bytes_per_sec < 1024**2: return f"{bytes_per_sec / 1024:.1f} KB/s"
        elif bytes_per_sec < 1024**3: return f"{bytes_per_sec / (1024**2):.1f} MB/s"
        else: return f"{bytes_per_sec / (1024**3):.2f} GB/s"

    # --- Lifecycle ---
    def showEvent(self, event):
        super().showEvent(event)
        if not self.thread.isRunning():
            self.worker._stop_event.clear()
            self.thread.start()
            self.graph_timer.start(16)
            self.card_timer.start(1000)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.window().isMinimized():
            return  # Skip shutdown - the app was just minimized
        self.graph_timer.stop()
        self.card_timer.stop()
        if hasattr(self, 'worker') and self.worker:
            self.worker._stop_event.set()
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def closeEvent(self, event: QCloseEvent):
        self.graph_timer.stop()
        self.card_timer.stop()
        if hasattr(self, 'worker') and self.worker:
            self.worker._stop_event.set()
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.wait(2000)
        super().closeEvent(event)

    def refresh_accent(self):
        self._read_graph.refresh_accent()
        self._write_graph.refresh_accent()
        self._space_card.refresh_accent()
        self._io_card.refresh_accent()