import hou
import sys

from PySide2.QtWidgets import (QLineEdit, QPushButton, QApplication,
    QVBoxLayout, QDialog, QMainWindow, QWidget, QGraphicsView, QGraphicsScene, QFrame, QGraphicsRectItem, QGraphicsItem, QGraphicsPathItem)

from PySide2.QtGui import QScreen, QPixmap, QBrush, QPen, QMouseEvent, QPainter, QColor, QFont, QCursor, QPainterPath, QImage, QGuiApplication

from PySide2.QtCore import Qt, QRect, QRectF, QPoint, QPointF

from importlib import reload

#<context> check in xml
def is_color_ramp(parms):
    if not parms:
        return False
    parm = parms[0]
    parm_template = parm.parmTemplate()

    if parm_template.type() == hou.parmTemplateType.Ramp and parm_template.parmType() == hou.rampParmType.Color:
        print(parm_template.parmType())
        return True

    return False

class ABMainScreen(QMainWindow):

    def __init__(self, parm, parent=None):

        super(ABMainScreen, self).__init__(parent)

        self.mouseX = [-1,-1]
        self.mouseY = [-1,-1]
        self.oldMouseX = [-1,-1]
        self.oldMouseY = [-1, -1]

        self._screens = []
        self._views = []
        self._scenes = []
        self._canvass = []

        self.configureScenes()

    def configureScenes(self):
        self._screenshots = [x.grabWindow(0) for x in QApplication.screens()] #Grab entire screen
        self._relscreenrect = [x.geometry() for x in QApplication.screens()]
        self._screens = QApplication.screens()


        for i, rect in enumerate(self._relscreenrect):
            self._views.append(QGraphicsView(self))
            self._views[i].setGeometry(rect)

            self._scenes.append(QGraphicsScene(self))
            self._canvass.append(self._screenshots[i].copy())

            self._scenes[i].addPixmap(self._canvass[i])
            self._views[i].setScene(self._scenes[i])

            self._views[i].setWindowFlags(Qt.FramelessWindowHint)
            self._views[i].setWindowFlags(Qt.WindowType_Mask)
            self._views[i].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._views[i].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

            # Capture our views and freeze it.
            self._views[i].showFullScreen()

    def closeCaptures(self):
        for view in self._views:
            view.close()

    def getMousePos(self, event):
        screen = QGuiApplication.screenAt(event.globalPos())
        screen_id = self._screens.index(screen)
        cursorloc = [event.globalPos().x() - screen.geometry().x(), event.globalPos().y() - screen.geometry().y()]
        self.mouseX = [screen_id, cursorloc[0]]
        self.mouseY = [screen_id, cursorloc[1]]

        return [screen_id, cursorloc[0], cursorloc[1]]

class SampleColor(ABMainScreen):

    def __init__(self, parent, parms):
        super(SampleColor, self).__init__(parent)
        self.colorparms = parms
        self.samplepositions = []

        for view in self._views:
            view.mouseMoveEvent = self.sampleColorAtMouse
            view.mouseReleaseEvent = self.populateRampAndExit

    def sampleColorAtMouse(self, event):
        _mousedata = self.getMousePos(event)
        self.samplepositions.append(_mousedata)
        self.update()

    def paintEvent(self, QPaintEvent):
        if self.oldMouseX[1] >= 0 and self.mouseX[1] >= 0:

            if self.oldMouseX[0] == self.mouseX[0]:

                pixmap = self._scenes[self.mouseX[0]].items()[0].pixmap().copy()
                painter = QPainter(pixmap)

                pen = QPen()
                pen.setWidth(2)
                pen.setColor(QColor('#FFCC4D'))

                painter.setPen(pen)
                painter.drawLine(self.oldMouseX[1], self.oldMouseY[1], self.mouseX[1], self.mouseY[1])
                painter.end()
                print('run')

                #Update pixmap
                self._scenes[self.mouseX[0]].items()[0].setPixmap(pixmap)

        self.oldMouseX = self.mouseX
        self.oldMouseY = self.mouseY

    def populateRampAndExit(self, event):

        bases = [hou.rampBasis.Linear] * len(self.samplepositions)
        print(bases)
        keys = [i/float(len(self.samplepositions)) for i, x in enumerate(self.samplepositions)]

        values = []

        for s, x, y in self.samplepositions:
            _color = QColor(self._screenshots[s].toImage().pixel(x,y))
            values.append((pow(_color.red()/255.0,2.2),pow(_color.green()/255.0,2.2),pow(_color.blue()/255.0,2.2)))

        self.colorparms.set(hou.Ramp(bases, keys, values))

        self.closeCaptures()
        self.close()

def show_gradient_picker(parm):
    eyeDropWindow = SampleColor(hou.qt.mainWindow(), parm)
    eyeDropWindow.show()