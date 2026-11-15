from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ui.data.network_worker import NetworkWorker, NetworkWorkerSnapshot
from ui.widgets.stat_card import StatCard
from ui.widgets.live_graph import LiveGraph

class NetworkPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(32, 32, 32, 32)
        self._layout.setSpacing(20)

        self._graph_layout = QHBoxLayout()
        self._graph_layout.setSpacing(20)

        self._down_graph = LiveGraph("Download Speed", "Speed (Mbps)", (0, 10))
        self._up_graph = LiveGraph("Upload Speed", "Speed (Mbps)", (0, 10))

        self._graph_layout.addWidget(self._down_graph)
        self._graph_layout.addWidget(self._up_graph)

        self._stats_layout = QHBoxLayout()
        self._stats_layout.setSpacing(20)
        
        self._info_card = StatCard("Connection", ["Interface", "Status"])
        self._traffic_card = StatCard("Live Traffic", ["Download", "Upload", "Total Data"])
        self._quality_card = StatCard("Link Quality", ["RX Errors", "TX Errors", "RX Drops", "TX Drops"])

        self._stats_layout.addWidget(self._info_card)
        self._stats_layout.addWidget(self._traffic_card)
        self._stats_layout.addWidget(self._quality_card)

        self._layout.addLayout(self._graph_layout, stretch=3)
        self._layout.addLayout(self._stats_layout, stretch=2)

        self._down_data = []
        self._up_data = []
        self._latest_snapshot = None  # Cache for the text cards

        self.thread = QThread()
        self.worker = NetworkWorker()
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self.thread.quit)
        
        # --- DUAL TIMERS ---
        # 1. Fast timer for smooth graphs (30ms = ~33 FPS)
        self.graph_timer = QTimer()
        self.graph_timer.timeout.connect(self.update_graphs)
        
        # 2. Slow timer for text cards (1000ms = 1 FPS)
        self.card_timer = QTimer()
        self.card_timer.timeout.connect(self.update_cards)
    
    def update_graphs(self):
        """Runs 33 times per second. Drains queue and draws lines."""
        pending = self.worker.drain_pending_snapshots()
        if not pending:
            return

        # Save the latest for the text cards
        self._latest_snapshot = pending[-1]

        for snapshot in pending:
            down_mbps = (snapshot.download_bps / 1_000_000) if snapshot.download_bps else 0.0
            up_mbps = (snapshot.upload_bps / 1_000_000) if snapshot.upload_bps else 0.0
            
            self._down_data.append(down_mbps)
            self._up_data.append(up_mbps)   

        self._down_data = self._down_data[-600:]
        self._up_data = self._up_data[-600:]

        # Update Graphs (Dynamic Y-Axis)
        max_down = max(self._down_data) if self._down_data else 0.0
        max_up = max(self._up_data) if self._up_data else 0.0

        self._down_graph.setYRange(0, max(10.0, max_down * 1.2), padding=0)
        self._up_graph.setYRange(0, max(10.0, max_up * 1.2), padding=0)  

        self._down_graph.set_data(self._down_data)
        self._up_graph.set_data(self._up_data)

    def update_cards(self):
        """Runs exactly 1 time per second. Updates text labels."""
        if not self._latest_snapshot:
            return
            
        latest = self._latest_snapshot

        # --- Update Cards ---
        if latest.interface:
            iface = "Wi-Fi" if "wi-fi" in latest.interface.lower() else latest.interface
            self._info_card.update_row("Interface", iface)
        else:
            self._info_card.update_row("Interface", "Offline")

        if latest.status:
            color = "#00ff00" if latest.status == "CONNECTED" else "#ff4444"
            self._info_card.update_row("Status", latest.status, color)
        else:
            self._info_card.update_row("Status", "--")

        self._traffic_card.update_row("Download", self._format_bits(latest.download_bps))
        self._traffic_card.update_row("Upload", self._format_bits(latest.upload_bps))
        
        if latest.total_bytes is not None:
            self._traffic_card.update_row("Total Data", self._format_bytes(latest.total_bytes))
        else:
            self._traffic_card.update_row("Total Data", "--")

        def err_str(val): return str(val) if val is not None else "0"
        def err_color(val): return "#ff4444" if val and val > 0 else "#00ff00"

        self._quality_card.update_row("RX Errors", err_str(latest.rx_errors), err_color(latest.rx_errors))
        self._quality_card.update_row("TX Errors", err_str(latest.tx_errors), err_color(latest.tx_errors))
        self._quality_card.update_row("RX Drops", err_str(latest.rx_drops), err_color(latest.rx_drops))
        self._quality_card.update_row("TX Drops", err_str(latest.tx_drops), err_color(latest.tx_drops))

    # --- Formatters ---
    def _format_bits(self, bits_per_sec: float | None) -> str:
        if bits_per_sec is None or bits_per_sec == 0:
            return "0 bps"
        if bits_per_sec < 1_000:
            return f"{bits_per_sec:.0f} bps"
        elif bits_per_sec < 1_000_000:
            return f"{bits_per_sec / 1_000:.1f} Kbps"
        elif bits_per_sec < 1_000_000_000:
            return f"{bits_per_sec / 1_000_000:.1f} Mbps"
        else:
            return f"{bits_per_sec / 1_000_000_000:.2f} Gbps"

    def _format_bytes(self, total_bytes: float | None) -> str:
        if total_bytes is None or total_bytes == 0:
            return "0 B"
        if total_bytes < 1024**2:
            return f"{total_bytes / 1024:.1f} KB"
        elif total_bytes < 1024**3:
            return f"{total_bytes / (1024**2):.1f} MB"
        else:
            return f"{total_bytes / (1024**3):.2f} GB"

    def showEvent(self, event):
        super().showEvent(event)
        if not self.thread.isRunning():
            self.worker._stop_event.clear()
            self.thread.start()
            
            # Start BOTH timers
            self.graph_timer.start(16) 
            self.card_timer.start(1000)  # 1 FPS for text

    def hideEvent(self, event):
        super().hideEvent(event)
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
        self._down_graph.refresh_accent()
        self._up_graph.refresh_accent()
        self._info_card.refresh_accent()
        self._traffic_card.refresh_accent()
        self._quality_card.refresh_accent()