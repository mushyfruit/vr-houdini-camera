from PySide2.QtCore import Qt, QRect, QEvent, QPoint, QTimer, QTime, QRectF, QPointF
from PySide2.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QWidget, QLabel, QGraphicsPixmapItem, QHBoxLayout, QGraphicsEllipseItem
from PySide2.QtGui import QColor, QPainter, QPen, QCursor, QPixmap, QGuiApplication, QPalette, QFont, QBrush
import hou, datetime, os, labutils
from importlib import reload

class ABRecordingOverlay(hou.qt.ViewerOverlay):
    def __init__(self, scene_viewer):
        super(ABRecordingOverlay, self).__init__(scene_viewer)

        print(self.size())
        hbox = QHBoxLayout()
        self.time_widget = overlayCountdown()
        #hbox.addWidget(self.time_widget)
        self.setLayout(hbox)

        #QGraphicsSetup
        vx, vy, vw, vh = self._scene_viewer.geometry()
        self.scene = QGraphicsScene(vx, vy, vw, vh)

        # Get bounds for circle
        size_val = min(vw, vh)
        ellipse_bounds = QRectF(vx, vy, size_val*5, size_val*5)
        ellipse_bounds.moveCenter(QPointF(vw/2.0, vh/2.0))
        thickness = 1
        
        self.ellipse = QGraphicsEllipseItem(ellipse_bounds)
        self.ellipse.setPen(QPen(Qt.white, thickness, Qt.SolidLine))
        self.ellipse.setBrush(QBrush(QColor(255, 255, 255, 25)))
        self.ellipse.setSpanAngle(0)
        self.scene.addItem(self.ellipse)

        view = QGraphicsView(self.scene)
        view.setWindowFlags(Qt.FramelessWindowHint)
        view.setWindowFlags(Qt.WindowType_Mask)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setStyleSheet('background-color: transparent')

        hbox.addWidget(view)

        self.timer = QTimer()
        self.time  = 3
        self.timer.timeout.connect(self.fire_off)
        self.time_widget.setText(str(self.time))

        self.leader_timer = QTimer()
        self.leader_timer.timeout.connect(self.leader_tick)
        self.leader_time = 0

        self.leader_timer.start(25)
        self.timer.start(1000) #Fire every 1s.


    def fire_off(self): 
        self.time -= 1
        self.time_widget.setText(str(self.time))
        if self.time <= 0:
            self.timer.stop()
            self.leader_timer.stop()
            self.close()

    def leader_tick(self):
        if (self.leader_time == 360):
            self.leader_time = 0
        self.leader_time += 9
        self.ellipse.setSpanAngle(self.leader_time * 16)

    def paintEvent(self, event):
        pass
        # vx,vy,vw,vh = self._scene_viewer.geometry()
        # scene = QGraphicsScene(vx, vy, vw, vh)
        # rect = QGraphicsRectItem(0, 0, 200, 50)
        # scene.addItem(rect)
        # view = QGraphicsView()
        # view.show()
        # painter = QPainter(self)
        # painter.setPen(QPen(Qt.white, 8, Qt.DashLine))
        # vx,vy,vw,vh = self._scene_viewer.geometry()
        # center = QPoint(vw/2.0, vh/2.0)
        # radius_val = min(vw, vh)/2.0
        # painter.drawEllipse(center, radius_val, radius_val)
        # painter.drawEllipse(center, radius_val/1.2, radius_val/1.2)

class overlayCountdown(QLabel):
    def __init__(self, parent=None):
        super(overlayCountdown, self).__init__(parent)
        self.setAlignment(Qt.AlignHCenter|Qt.AlignVCenter)
        self.setFont(QFont('Arial', 300))
        self.setText("Countdown")

def begin_overlay():
    viewport = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    #view_window = hou.qt.ViewerOverlay(viewport)
    win = ABRecordingOverlay(viewport)
    win.show()

