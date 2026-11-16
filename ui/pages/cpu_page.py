from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ui.data.cpu_worker import CpuWorker
from ui.widgets.stat_card import StatCard
from ui.widgets.live_graph import LiveGraph


class CpuPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_temp = 0.0

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(32, 32, 32, 32)
        self._layout.setSpacing(20)

        # 1. Setup Graphs
        self._graph_layout = QHBoxLayout()
        self._graph_layout.setSpacing(20)
        
        self._usage_graph = LiveGraph("CPU Utilization", "Usage (%)", (0, 100))
        self._freq_graph = LiveGraph("CPU Frequency", "Frequency (GHz)", (0, 5))
        
        self._graph_layout.addWidget(self._usage_graph)
        self._graph_layout.addWidget(self._freq_graph)

        # 2. Setup Stat Cards
        self._stats_layout = QHBoxLayout()
        self._stats_layout.setSpacing(20)
        self._info_card = StatCard("Processor Info", ["Name", "Vendor", "Base Speed"])
        self._metrics_card = StatCard("Live Metrics", ["Live Speed", "Current Temp", "Max Temp"])
        self._stats_layout.addWidget(self._info_card)
        self._stats_layout.addWidget(self._metrics_card)

        self._layout.addLayout(self._graph_layout, stretch=3)
        self._layout.addLayout(self._stats_layout, stretch=1)

        # 3. Data & Threading
        self._usage_data = []
        self._freq_data = []

        self.thread = QThread()
        self.worker = CpuWorker()
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
            usage = snapshot.cpu_usage_pct if snapshot.cpu_usage_pct is not None else 0.0
            freq_ghz = (snapshot.cpu_freq_mhz / 1000.0) if snapshot.cpu_freq_mhz is not None else 0.0
            self._usage_data.append(usage)
            self._freq_data.append(freq_ghz)

        self._usage_data = self._usage_data[-600:]
        self._freq_data = self._freq_data[-600:]

        latest = pending[-1] 
        
        if latest.cpu_name:
            self._info_card.update_row("Name", latest.cpu_name)
        if latest.cpu_vendor:
            self._info_card.update_row("Vendor", latest.cpu_vendor)
        if latest.cpu_base_speed_mhz is not None:
            self._info_card.update_row("Base Speed", f"{latest.cpu_base_speed_mhz / 1000:.2f} GHz")
            
        if latest.cpu_freq_mhz is not None:
            self._metrics_card.update_row("Live Speed", f"{latest.cpu_freq_mhz / 1000:.2f} GHz")
            
        if latest.cpu_temp is not None:
            self._metrics_card.update_row("Current Temp", f"{latest.cpu_temp:.1f} °C")
            if latest.cpu_temp > self._max_temp:
                self._max_temp = latest.cpu_temp
                color = "#ff4444" if self._max_temp > 85 else None
                self._metrics_card.update_row("Max Temp", f"{self._max_temp:.1f} °C", color)
            
        self._usage_graph.set_data(self._usage_data)
        self._freq_graph.set_data(self._freq_data)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.thread.isRunning():
            self.worker._stop_event.clear()
            self.thread.start()
            self.timer.start(16) 

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.window().isMinimized():
            return
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

    def refresh_theme(self):
        self._usage_graph.refresh_theme()
        self._freq_graph.refresh_theme()
        self._info_card.refresh_theme()
        self._metrics_card.refresh_theme()