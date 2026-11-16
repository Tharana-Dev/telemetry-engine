import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from ui.personalization import current_theme


class LiveGraph(pg.PlotWidget):
    """A reusable, glowing, real-time graph for telemetry data."""
    def __init__(self, title: str, y_label: str, y_range: tuple[float, float], parent=None):
        super().__init__(parent)
        
        theme = current_theme()
        
        # 1. Base setup
        self.setBackground(theme.bg)
        self.setTitle(f"<span style='color: {theme.text}; font-size: 12pt; font-weight: 800;'>{title.upper()}</span>")
        self.showGrid(x=True, y=True, alpha=0.1)
        self.setMouseEnabled(x=False, y=False)
        self.setYRange(y_range[0], y_range[1], padding=0)
        self.setXRange(-60, 0, padding=0)
        
        # 2. Style the axes
        for axis in ['left', 'bottom']:
            ax = self.getAxis(axis)
            ax.setPen(theme.border)
            ax.setTextPen(theme.text)
            ax.setStyle(tickLength=0)
            
        self.setLabel('left', y_label.upper(), color=theme.text, **{'font-size': '10pt', 'font-weight': 'bold'})
        self.setLabel('bottom', "TIME (SEC)", color=theme.text, **{'font-size': '10pt', 'font-weight': 'bold'})
        
        # 3. Create the curves
        self._main_curve = self.plot()
        self._glow_curve = self.plot()
        
        # 4. Apply initial colors
        self.refresh_theme()

    def set_data(self, data: list[float]):
        """Updates the graph with a list of values (max 600 points)."""
        if not data:
            return
            
        x = np.linspace(-len(data) / 10.0, 0, len(data))
        
        self._main_curve.setData(x, data)
        self._glow_curve.setData(x, data)

    def refresh_theme(self):
        """Updates the graph colors when the theme changes."""
        theme = current_theme()
        
        # Background and title
        self.setBackground(theme.bg)
        
        # Main line
        main_pen = pg.mkPen(color=theme.highlight, width=2)
        fill_color = pg.mkColor(theme.highlight)
        fill_color.setAlpha(30)
        self._main_curve.setPen(main_pen)
        self._main_curve.setBrush(pg.mkBrush(fill_color))
        self._main_curve.setFillLevel(0)
        
        # Glow line (thick and transparent)
        glow_pen = pg.mkPen(color=theme.highlight, width=6)
        glow_color = QColor(theme.highlight)
        glow_color.setAlpha(50)
        glow_pen.setColor(glow_color)
        self._glow_curve.setPen(glow_pen)
        
        # Axes
        for axis in ['left', 'bottom']:
            ax = self.getAxis(axis)
            ax.setPen(theme.border)
            ax.setTextPen(theme.text)