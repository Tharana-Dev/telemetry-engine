import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from ui.theme import ThemeColors
from ui.personalization import current_accent

class LiveGraph(pg.PlotWidget):
    """A reusable, glowing, real-time graph for telemetry data."""
    def __init__(self, title: str, y_label: str, y_range: tuple[float, float], parent=None):
        super().__init__(parent)
        
        # 1. Base setup
        self.setBackground(ThemeColors.BG_BASE)
        self.setTitle(f"<span style='color: {ThemeColors.TEXT_PRIMARY}; font-size: 12pt; font-weight: 800;'>{title.upper()}</span>")
        self.showGrid(x=True, y=True, alpha=0.1)
        self.setMouseEnabled(x=False, y=False)
        self.setYRange(y_range[0], y_range[1], padding=0)
        
        # We will plot negative seconds (-60s to 0s)
        self.setXRange(-60, 0, padding=0)
        
        # 2. Style the axes
        for axis in ['left', 'bottom']:
            ax = self.getAxis(axis)
            ax.setPen(ThemeColors.BORDER_SUBTLE)
            ax.setTextPen(ThemeColors.TEXT_MUTED)
            ax.setStyle(tickLength=0)
            
        self.setLabel('left', y_label.upper(), **{'color': ThemeColors.TEXT_MUTED, 'font-size': '10pt', 'font-weight': 'bold'})
        self.setLabel('bottom', "TIME (SEC)", **{'color': ThemeColors.TEXT_MUTED, 'font-size': '10pt', 'font-weight': 'bold'})
        
        # 3. Create the curves (Glow + Main)
        self._main_curve = self.plot()
        self._glow_curve = self.plot()
        
        # 4. Apply initial colors
        self.refresh_accent()

    def set_data(self, data: list[float]):
        """Updates the graph with a list of values (max 600 points)."""
        if not data:
            return
            
        # Calculate X-axis as negative seconds (-60 to 0)
        # Assuming 10 points per second (0.1s interval from worker)
        x = np.linspace(-len(data) / 10.0, 0, len(data))
        
        self._main_curve.setData(x, data)
        self._glow_curve.setData(x, data)

    def refresh_accent(self):
        """Updates the graph colors when the theme changes."""
        accent_hex = current_accent().primary
        
        # Main line
        main_pen = pg.mkPen(color=accent_hex, width=2)
        fill_color = pg.mkColor(accent_hex)
        fill_color.setAlpha(30)
        self._main_curve.setPen(main_pen)
        self._main_curve.setBrush(pg.mkBrush(fill_color))
        self._main_curve.setFillLevel(0)
        
        # Glow line (thick and transparent)
        glow_pen = pg.mkPen(color=accent_hex, width=6)
        glow_color = QColor(accent_hex)
        glow_color.setAlpha(50)
        glow_pen.setColor(glow_color)
        self._glow_curve.setPen(glow_pen)