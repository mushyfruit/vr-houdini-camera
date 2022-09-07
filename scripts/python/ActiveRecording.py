from PySide2.QtCore import Qt, QRect, QEvent, QPoint, QTimer, QTime, QRectF, QPointF, Signal, QPropertyAnimation, QAbstractAnimation, QElapsedTimer
from PySide2.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QWidget, QLabel, QGraphicsPixmapItem, QHBoxLayout, QGraphicsOpacityEffect, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsRectItem
from PySide2.QtGui import QColor, QPainter, QPen, QCursor, QPixmap, QGuiApplication, QPalette, QFont, QBrush, QFontMetricsF
import hou, datetime, os, labutils

class SimpleRecorderOverlay(hou.qt.ViewerOverlay):

    def __init__(self, scene_viewer):
        super(SimpleRecorderOverlay, self).__init__(scene_viewer)

        #layout initialized to scene viewer bounds, no margins.
        hbox = QHBoxLayout()
        self.setLayout(hbox)
        hbox.setContentsMargins(0,0,0,0)

        #QGraphicsSetup
        vx, vy, vw, vh = self._scene_viewer.geometry()
        self.scene = QGraphicsScene(vx, vy, vw, vh)

        #offset val
        circle_offset = 50

        #Add Text
        self.text = QGraphicsTextItem("REC")
        self.text.setFont(QFont('Arial', 25))
        center_loc = self.text.boundingRect().center()

        font_metric = QFontMetricsF(self.text.font())
        cur_size = font_metric.tightBoundingRect(self.text.toPlainText().upper())
        c_height = cur_size.height()

        #Text Location
        self.text.setY(vy + c_height)
        self.text.setX(vx + circle_offset + cur_size.width()/2.0 - 8.0)

        #Circle bounds
        circle_bounds = QRectF(vx + circle_offset, vy + circle_offset, c_height, c_height)
        recording_circle = QGraphicsEllipseItem(circle_bounds)
        circle_brush = QBrush(QColor(255, 0, 0, 255))
        recording_circle.setBrush(circle_brush)

        #Create a pulsing opacity effect.
        flicker = QGraphicsOpacityEffect()
        recording_circle.setGraphicsEffect(flicker)
        self.opac = QPropertyAnimation(flicker, b"opacity")
        self.opac.setDuration(1000)
        self.opac.setStartValue(0.5)
        self.opac.setEndValue(1)
        self.opac.finished.connect(self.bounce)
        self.opac.start()

        self.scene.addItem(recording_circle)

        #Create a timer text object in bottom right
        text = "00:00:00"
        self.timer_text = QGraphicsTextItem(text)
        self.timer_text.setFont(QFont('Arial', 20))

        font_metric = QFontMetricsF(self.timer_text.font())
        timer_size = font_metric.tightBoundingRect(self.timer_text.toPlainText().upper())

        #Place timer in the middle of the screen.
        self.timer_text.setY(vh - vh/20.0 - timer_size.height())
        self.timer_text.setX(vw/2.0 - timer_size.width()/2.0)
        self.scene.addItem(self.timer_text)

        #Create timer object.
        self.timer = QElapsedTimer()
        self.timer.start()

        self.update_timer = QTimer()
        self.update_timer.start(25)
        self.update_timer.timeout.connect(self.timer_tick)

        self.display_time = QTime()
        self.display_time.setHMS(0,0,0,0)


        #Create the Graphics View to render the QGraphics.
        view = QGraphicsView(self.scene)
        #Enable AA
        view.setRenderHint(QPainter.Antialiasing)
        view.setRenderHint(QPainter.TextAntialiasing)
        view.setRenderHint(QPainter.SmoothPixmapTransform)

        self.scene.addItem(self.text)

        #Set Flags and make Transparent
        view.setWindowFlags(Qt.FramelessWindowHint)
        view.setWindowFlags(Qt.WindowType_Mask)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setStyleSheet('background-color: transparent')

        hbox.addWidget(view)

    def bounce(self):
        if(self.opac.direction() == QAbstractAnimation.Direction.Forward):
            self.opac.setDirection(QAbstractAnimation.Direction.Backward)
            self.opac.start()
        else:
            self.opac.setDirection(QAbstractAnimation.Direction.Forward)
            self.opac.start()

    def timer_tick(self):
        milliseconds = self.timer.elapsed()
        seconds = milliseconds / 1000;
        milliseconds = milliseconds % 1000
        minutes = seconds / 60
        seconds = seconds % 60

        self.display_time.setHMS(0, minutes, seconds, milliseconds)

        d_text = self.display_time.toString("mm:ss:z")
        #Only display two digits of milli
        if(len(d_text) == 9):
            d_text = d_text[:8]
        self.timer_text.setPlainText(d_text)


    def stop_timers(self):
        self.update_timer.stop()

def begin_overlay():
    viewport = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    #view_window = hou.qt.ViewerOverlay(viewport)
    win = SimpleRecorderOverlay(viewport)
    return win

