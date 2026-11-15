from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ui.data.memory_worker import MemoryWorker, MemoryWorkerSnapshot
from ui.widgets.stat_card import StatCard
from ui.widgets.live_graph import LiveGraph

class MemoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(32, 32, 32, 32)
        self._layout.setSpacing(20)

        self._graph_layout = QHBoxLayout()
        self._graph_layout.setSpacing(20)  

        self._pct_graph = LiveGraph("Memory Utilization", "Usage (%)", (0, 100))
        self._gb_graph = LiveGraph("Memory Allocation", "Used (GB)", (0, 16))

        self._graph_layout.addWidget(self._pct_graph)
        self._graph_layout.addWidget(self._gb_graph)

        self._stats_layout = QHBoxLayout()
        self._stats_layout.setSpacing(20)
        
        self._overview_card = StatCard("Memory Overview", ["Used", "Total", "Usage"])
        self._details_card = StatCard("Memory Details", ["Available", "Status"])
        
        self._stats_layout.addWidget(self._overview_card)
        self._stats_layout.addWidget(self._details_card)

        self._layout.addLayout(self._graph_layout, stretch=3)
        self._layout.addLayout(self._stats_layout, stretch=1) 

        self._pct_data = []
        self._gb_data = []
        self._has_set_y_axis = False

        self.thread = QThread()
        self.worker = MemoryWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self.thread.quit)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_graphs)

    def update_graphs(self):
        pending = self.worker.drain_pending_snapshots()
        if not pending:
            return

        for snapshot in pending:
            pct = snapshot.used_pct if snapshot.used_pct is not None else 0.0
            gb = snapshot.used_gb if snapshot.used_gb is not None else 0.0
            self._pct_data.append(pct)
            self._gb_data.append(gb)

        self._pct_data = self._pct_data[-600:]
        self._gb_data = self._gb_data[-600:]

        latest = pending[-1] 

        # --- Update Cards ---
        if latest.used_gb is not None:
            self._overview_card.update_row("Used", f"{latest.used_gb:.1f} GB")
        else:
            self._overview_card.update_row("Used", "--")
            
        if latest.total_gb is not None:
            self._overview_card.update_row("Total", f"{latest.total_gb:.1f} GB")
            
            # Dynamic Y-Axis: The first time we get total_gb, adjust the GB graph's Y-axis
            if not self._has_set_y_axis:
                self._gb_graph.setYRange(0, latest.total_gb, padding=0)
                self._has_set_y_axis = True
        else:
            self._overview_card.update_row("Total", "--")
            
        if latest.used_pct is not None:
            color = "#ff4444" if latest.used_pct > 85 else ("#ffbb33" if latest.used_pct > 60 else None)
            self._overview_card.update_row("Usage", f"{latest.used_pct:.1f}%", color)
        else:
            self._overview_card.update_row("Usage", "--")

        if latest.available_gb is not None:
            self._details_card.update_row("Available", f"{latest.available_gb:.1f} GB")
        else:
            self._details_card.update_row("Available", "--")
            
        # Fun little status indicator
        if latest.used_pct is not None:
            status = "Stable" if latest.used_pct < 80 else "High Load"
            color = "#00ff00" if latest.used_pct < 80 else "#ff4444"
            self._details_card.update_row("Status", status, color)

        # --- Update Graphs ---
        self._pct_graph.set_data(self._pct_data)
        self._gb_graph.set_data(self._gb_data)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.thread.isRunning():
            self.worker._stop_event.clear()
            self.thread.start()
            self.timer.start(16)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()

        if hasattr(self, 'worker') and self.worker:
            self.worker._stop_event.set()

        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
    
    def closeEvent(self, event: QCloseEvent):
        self.timer.stop()
        if hasattr(self, 'worker') and self.worker:
            self.worker._stop_event.set()
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.wait(2000)
        super().closeEvent(event)

    def refresh_accent(self):
        self._pct_graph.refresh_accent()
        self._gb_graph.refresh_accent()

        self._overview_card.refresh_accent()
        self._details_card.refresh_accent()
        