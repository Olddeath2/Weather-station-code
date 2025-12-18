# windcompass.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QBrush, QFont
from PyQt5.QtCore import Qt, QPointF
import math

class WindCompass(QWidget):
    """
    Simple compass widget:
    - Draws a circular compass with N/E/S/W labels
    - Draws tick marks for every 45°
    - Draws a needle rotated to given degrees (0 = North)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle_deg = 0.0  # 0 = North
        self.setMinimumSize(120, 120)

    def setDirection(self, degrees: float):
        """Set needle angle in degrees (0 = North)."""
        self._angle_deg = degrees % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        size = min(w, h)
        radius = size * 0.42
        center = QPointF(w/2, h/2)

        # Background circle
        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(Qt.white))
        painter.drawEllipse(center, radius, radius)

        # Draw ticks every 45°, small ticks every 15°
        painter.setPen(QPen(Qt.black, 1))
        for deg in range(0, 360, 15):
            angle_rad = math.radians(-deg + 90)
            outer = QPointF(center.x() + math.cos(angle_rad) * radius,
                            center.y() - math.sin(angle_rad) * radius)
            inner_len = 0.92 if deg % 45 == 0 else 0.96
            inner = QPointF(center.x() + math.cos(angle_rad) * (radius * inner_len),
                            center.y() - math.sin(angle_rad) * (radius * inner_len))
            painter.drawLine(inner, outer)

        # Cardinal labels
        font = QFont()
        font.setBold(True)
        font.setPointSize(max(8, int(size * 0.06)))
        painter.setFont(font)
        fm = painter.fontMetrics()

        # N
        n_pt = QPointF(center.x() - fm.horizontalAdvance("N")/2, center.y() - radius + fm.height())
        painter.drawText(n_pt, "N")
        # S
        s_pt = QPointF(center.x() - fm.horizontalAdvance("S")/2, center.y() + radius - 4)
        painter.drawText(s_pt, "S")
        # E
        e_pt = QPointF(center.x() + radius - fm.horizontalAdvance("E") - 4, center.y() + fm.height()/4)
        painter.drawText(e_pt, "E")
        # W
        w_pt = QPointF(center.x() - radius + 4, center.y() + fm.height()/4)
        painter.drawText(w_pt, "W")

        # Needle (rotated)
        painter.setPen(QPen(Qt.red, 2))
        painter.setBrush(QBrush(Qt.red))

        # angle conversion: 0° = North (straight up). QPainter uses +x right, +y down.
        angle_rad = math.radians(-self._angle_deg + 90)

        needle_length = radius * 0.82
        tip = QPointF(center.x() + math.cos(angle_rad) * needle_length,
                      center.y() - math.sin(angle_rad) * needle_length)

        # Draw needle as a triangle for nicer look
        side_angle1 = angle_rad + math.radians(90)
        side_angle2 = angle_rad - math.radians(90)
        side_offset = radius * 0.08

        p1 = tip
        p2 = QPointF(center.x() + math.cos(side_angle1) * side_offset,
                     center.y() - math.sin(side_angle1) * side_offset)
        p3 = QPointF(center.x() + math.cos(side_angle2) * side_offset,
                     center.y() - math.sin(side_angle2) * side_offset)

        # Painted as polygon
        painter.drawPolygon(p1, p2, p3)

        # Draw small center circle
        painter.setBrush(QBrush(Qt.black))
        painter.setPen(QPen(Qt.black))
        painter.drawEllipse(center, max(3, int(size * 0.02)), max(3, int(size * 0.02)))
