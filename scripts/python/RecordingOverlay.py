from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal, QElapsedTimer
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QLabel, QHBoxLayout, QGraphicsEllipseItem, QGraphicsTextItem
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QBrush

import hou


class ABRecordingOverlay(hou.qt.ViewerOverlay):

    Recording_Call = Signal(int)

    def __init__(self, scene_viewer):
        super().__init__(scene_viewer)

        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)

        _, _, width, height = self._scene_viewer.geometry()
        self.scene = QGraphicsScene(0, 0, width, height, self)

        size = min(width, height)
        center = QPointF(width / 2.0, height / 2.0)
        ellipse_bounds = QRectF(0, 0, size * 5, size * 5)
        ellipse_bounds.moveCenter(center)
        thickness = 4

        self.ellipse = QGraphicsEllipseItem(ellipse_bounds)
        self.ellipse.setPen(QPen(Qt.GlobalColor.white, thickness, Qt.PenStyle.SolidLine))
        self.ellipse.setBrush(QBrush(QColor(255, 255, 255, 25)))
        self.ellipse.setSpanAngle(0)
        self.scene.addItem(self.ellipse)

        self.text = QGraphicsTextItem("3")
        self.text.setFont(QFont("Arial", 300))
        text_center = self.text.boundingRect().center()

        ellipse_pen = QPen(Qt.GlobalColor.white, thickness, Qt.PenStyle.SolidLine)
        for diameter in (size / 2.0, size / 1.5):
            bounds = QRectF(0, 0, diameter, diameter)
            bounds.moveCenter(center)
            self.scene.addEllipse(bounds, ellipse_pen)

        self.text.setPos(center - text_center)
        self.scene.addItem(self.text)

        view = QGraphicsView(self.scene)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        view.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setStyleSheet("background: transparent; border: 0")
        hbox.addWidget(view)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fire_off)
        self.time = 3
        self.text.setPlainText(str(self.time))

        self.leader = QElapsedTimer()
        self.leader.start()
        self.leader_timer = QTimer(self)
        self.leader_timer.timeout.connect(self.leader_tick)
        self.leader_timer.start(25)
        self.timer.start(1000)

    def fire_off(self):
        self.time -= 1
        self.text.setPlainText(str(self.time))
        if self.time <= 0:
            self.timer.stop()
            self.Recording_Call.emit(0)
            self.close()

    def leader_tick(self):
        elapsed = self.leader.elapsed()
        self.ellipse.setSpanAngle((elapsed % 1000) * 360 * 16 // 1000)

    def closeEvent(self, event):
        self.timer.stop()
        self.leader_timer.stop()
        super().closeEvent(event)


class overlayCountdown(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.setFont(QFont("Arial", 300))
        self.setText("Countdown")


def begin_overlay():
    return ABRecordingOverlay(hou.ui.paneTabOfType(hou.paneTabType.SceneViewer))
