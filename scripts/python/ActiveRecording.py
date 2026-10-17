from PySide6.QtCore import Qt, QTimer, QRectF, QElapsedTimer, QPropertyAnimation, QAbstractAnimation
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QHBoxLayout, QGraphicsOpacityEffect, QGraphicsEllipseItem, QGraphicsTextItem
from PySide6.QtGui import QColor, QPainter, QFont, QBrush, QFontMetricsF

import hou


class SimpleRecorderOverlay(hou.qt.ViewerOverlay):

    def __init__(self, scene_viewer):
        super().__init__(scene_viewer)

        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)

        _, _, width, height = self._scene_viewer.geometry()
        self.scene = QGraphicsScene(0, 0, width, height, self)

        circle_offset = 50
        self.text = QGraphicsTextItem("REC")
        self.text.setFont(QFont("Arial", 25))
        text_size = QFontMetricsF(self.text.font()).tightBoundingRect(self.text.toPlainText())
        self.text.setPos(circle_offset + text_size.width() / 2.0 - 8.0, text_size.height())

        circle_bounds = QRectF(circle_offset, circle_offset, text_size.height(), text_size.height())
        recording_circle = QGraphicsEllipseItem(circle_bounds)
        recording_circle.setBrush(QBrush(QColor(255, 0, 0)))

        self.flicker = QGraphicsOpacityEffect()
        recording_circle.setGraphicsEffect(self.flicker)
        self.opac = QPropertyAnimation(self.flicker, b"opacity", self)
        self.opac.setDuration(1000)
        self.opac.setStartValue(0.5)
        self.opac.setEndValue(1)
        self.opac.finished.connect(self.bounce)
        self.opac.start()

        self.scene.addItem(recording_circle)
        self.scene.addItem(self.text)

        self.timer_text = QGraphicsTextItem("00:00:00")
        self.timer_text.setFont(QFont("Arial", 20))
        timer_size = QFontMetricsF(self.timer_text.font()).tightBoundingRect(self.timer_text.toPlainText())
        self.timer_text.setPos(width / 2.0 - timer_size.width() / 2.0, height - height / 20.0 - timer_size.height())
        self.scene.addItem(self.timer_text)

        self.timer = QElapsedTimer()
        self.timer.start()
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.timer_tick)
        self.update_timer.start(25)

        view = QGraphicsView(self.scene)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        view.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setStyleSheet("background: transparent; border: 0")
        hbox.addWidget(view)

    def bounce(self):
        direction = QAbstractAnimation.Direction.Backward if self.opac.direction() == QAbstractAnimation.Direction.Forward else QAbstractAnimation.Direction.Forward
        self.opac.setDirection(direction)
        self.opac.start()

    def timer_tick(self):
        elapsed = self.timer.elapsed()
        minutes, seconds = divmod(elapsed // 1000, 60)
        self.timer_text.setPlainText(f"{minutes:02d}:{seconds:02d}:{elapsed % 1000 // 10:02d}")

    def stop_timers(self):
        self.update_timer.stop()
        self.opac.stop()

    def closeEvent(self, event):
        self.stop_timers()
        super().closeEvent(event)


def begin_overlay():
    return SimpleRecorderOverlay(hou.ui.paneTabOfType(hou.paneTabType.SceneViewer))
