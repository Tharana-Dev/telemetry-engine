from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QGridLayout

from ui.data.gpu_worker import GpuWorker, GpuWorkerSnapshot
from ui.widgets.stat_card import StatCard
from ui.widgets.live_graph import LiveGraph

class GpuPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(32, 32, 32, 32)
        self._layout.setSpacing(20)

        # 1. Graphs (Temperature is reliable, Utilization is best-effort)
        self._graph_layout = QHBoxLayout()
        self._graph_layout.setSpacing(20)

        self._temp_graph = LiveGraph("GPU Temperature", "Temp (°C)", (30, 100))
        self._util_graph = LiveGraph("GPU Utilization", "Usage (%)", (0, 100))

        self._graph_layout.addWidget(self._temp_graph)
        self._graph_layout.addWidget(self._util_graph)

        # 2. Dynamic Stat Cards Container
        self._cards_container = QWidget()
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(20)
        
        self._gpu_cards = {} # Store dynamically created cards by GPU index

        self._layout.addLayout(self._graph_layout, stretch=3)
        self._layout.addWidget(self._cards_container, stretch=2)

        # 3. Data & Threading
        self._temp_data = []
        self._util_data = []
        self._latest_snapshot = None

        self.thread = QThread()
        self.worker = GpuWorker()
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self.thread.quit)
        
        self.graph_timer = QTimer()
        self.graph_timer.timeout.connect(self.update_graphs)
        
        self.card_timer = QTimer()
        self.card_timer.timeout.connect(self.update_cards)

    def _build_cards_if_needed(self, snapshot: GpuWorkerSnapshot):
        """Dynamically builds StatCards for each detected GPU."""
        if snapshot.gpus and not self._gpu_cards:
            # Clear placeholder if any
            while self._cards_layout.count():
                item = self._cards_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Create a card for each GPU
            for idx, gpu in enumerate(snapshot.gpus):
                name = gpu.name or f"GPU {idx}"
                
                card = StatCard(f"dGPU {idx}: {name}", ["Temp", "Utilization", "Power", "Fan Speed"])
                self._cards_layout.addWidget(card, 0, idx)
                self._gpu_cards[gpu.index] = card
            
            # If no dGPU is found, show iGPU info
            if not snapshot.gpus and snapshot.igpu_name:
                card = StatCard("Integrated GPU", ["Name", "Status"])
                card.update_row("Name", snapshot.igpu_name)
                card.update_row("Status", "Active (Admin Required for stats)", "#ffbb33")
                self._cards_layout.addWidget(card, 0, 0)
                self._gpu_cards[-1] = card 

    def update_graphs(self):
        pending = self.worker.drain_pending_snapshots()
        if not pending:
            return

        self._latest_snapshot = pending[-1]
        self._build_cards_if_needed(self._latest_snapshot)

        for snapshot in pending:
            if snapshot.gpus:
                gpu = snapshot.gpus[0]
                # If Temp/Util is None, default to 0 for the graph
                temp = gpu.temperature_c if gpu.temperature_c is not None else 0.0
                util = gpu.utilization_pct if gpu.utilization_pct is not None else 0.0
                
                self._temp_data.append(temp)
                self._util_data.append(util)
            else:
                # If no GPU, keep the graph flat
                self._temp_data.append(0.0)
                self._util_data.append(0.0)

        self._temp_data = self._temp_data[-600:]
        self._util_data = self._util_data[-600:]

        self._temp_graph.set_data(self._temp_data)
        self._util_graph.set_data(self._util_data)

    def update_cards(self):
        if not self._latest_snapshot or not self._latest_snapshot.gpus:
            return

        for gpu in self._latest_snapshot.gpus:
            card = self._gpu_cards.get(gpu.index)
            if card:
                # Temp (Reliable)
                if gpu.temperature_c is not None:
                    color = "#ff4444" if gpu.temperature_c > 85 else None
                    card.update_row("Temp", f"{gpu.temperature_c} °C", color)
                else:
                    card.update_row("Temp", "--")

                # Utilization (Best Effort)
                if gpu.utilization_pct is not None:
                    card.update_row("Utilization", f"{gpu.utilization_pct}%")
                else:
                    card.update_row("Utilization", "--")

                # Power (Best Effort)
                if gpu.power_w is not None:
                    card.update_row("Power", f"{gpu.power_w:.1f} W")
                else:
                    card.update_row("Power", "--")

                # Fan Speed (Best Effort)
                if gpu.fan_speed_pct is not None:
                    card.update_row("Fan Speed", f"{gpu.fan_speed_pct}%")
                else:
                    card.update_row("Fan Speed", "--")

    # --- Lifecycle ---
    def showEvent(self, event):
        super().showEvent(event)
        if not self.thread.isRunning():
            self.worker._stop_event.clear()
            self.thread.start()
            self.graph_timer.start(30)
            self.card_timer.start(1000)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.window().isMinimized():
            return
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
        self._temp_graph.refresh_accent()
        self._util_graph.refresh_accent()
        for card in self._gpu_cards.values():
            card.refresh_accent()