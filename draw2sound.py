import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QColorDialog, QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt5.QtCore import Qt
import numpy as np
import sounddevice as sd
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
import pyaudio
from astropy.convolution import convolve, Box1DKernel
from scipy.io.wavfile import write

class DrawingPad(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle('draw2sound')
        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self.createButtons()
        self.show()

    def createButtons(self):
        # Clear Sound button
        clearButton = QPushButton('Clear', self)
        clearButton.clicked.connect(self.canvas.clearCanvas)
        clearButton.setGeometry(10, 10, 100, 30)
        clearButton.setStyleSheet("background-color: red;")

        # Play sound button
        playSoundButton = QPushButton('Play Sound', self)
        playSoundButton.clicked.connect(self.canvas.playSound)
        playSoundButton.setGeometry(120, 10, 100, 30)

class Canvas(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(0, 0, 800, 600)
        self.setMouseTracking(True)
        self.drawingEnabled = True 
        self.pen = QPen(Qt.black, 2)
        self.path = QPainterPath()
        self.lastPoint = None
        self.x_values = []
        self.y_values = []
        self.mouse_position_label = QLabel(self)
        self.mouse_position_label.move(10, 10)  
        self.mouse_position_label.setText("Mouse Position: (0, 0)")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.pen)
        painter.drawPath(self.path)
        
        gridSize = 20  
        gridColor = Qt.gray  
        gridStyle = Qt.DotLine  
   
        painter.setPen(QPen(gridColor, 1, gridStyle))
        for i in range(0, self.height() // 2, gridSize):
            painter.drawLine(0, self.height() // 2 + i, self.width(), self.height() // 2 + i)
            painter.drawLine(0, self.height() // 2 - i, self.width(), self.height() // 2 - i)    

        for j in range(0, self.width() // 2, gridSize):
            painter.drawLine(self.width() // 2 + j, 0, self.width() // 2 + j, self.height())
            painter.drawLine(self.width() // 2 - j, 0, self.width() // 2 - j, self.height())
            
        centerLineThickness = 2  
        painter.setPen(QPen(gridColor, centerLineThickness, gridStyle))
        painter.drawLine(0, self.height() // 2, self.width(), self.height() // 2)
        painter.drawLine(self.width() // 2, 0, self.width() // 2, self.height())

    def mousePressEvent(self, event):
        if self.drawingEnabled and event.button() == Qt.LeftButton:
            self.lastPoint = event.pos()
            self.path.moveTo(self.lastPoint)
            self.add_point(event.pos())

    def mouseMoveEvent(self, event):
        x = event.x() - self.width() / 2
        y = event.y() - self.height() / 2
        self.mouse_position_label.setText(f"({x}, {y})")
        if self.drawingEnabled and event.buttons() & Qt.LeftButton:
            if event.pos().x() > self.lastPoint.x():
                self.path.lineTo(event.pos())
                self.update()
                self.lastPoint = event.pos()
                self.add_point(event.pos())
        
    def mouseReleaseEvent(self, event):
        if self.drawingEnabled and event.button() == Qt.LeftButton:
            self.path.lineTo(event.pos())
            self.update()
            self.drawingEnabled = False 

    def clearCanvas(self):
        self.path = QPainterPath()
        self.update()
        self.drawingEnabled = True
        self.x_values = []
        self.y_values = []

    def add_point(self, pos):
        self.x_values.append(pos.x() - self.width() / 2)
        self.y_values.append(pos.y() - self.height() / 2)

    def playSound(self):
        x = self.x_values 
        y = np.array(self.y_values)

        max_norm = np.max(np.abs(y))
        wave = y / max_norm
        waveform = y / max_norm
        N = len(wave)
        frequency = round(110)
        duration = 2
        sampling_freq = N*frequency 
        amplitude = 1
        for i in range(duration):
            for j in range(frequency):
                waveform = np.concatenate((waveform, wave))
        waveform = -1 * amplitude * waveform
        # Smooth out the signal
        w = 10 # Points to average
        waveform = convolve(waveform, Box1DKernel(w))
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32, channels=2, rate=sampling_freq, output=True)
        stream.write(waveform.astype(np.float32).tobytes())
        stream.close()
        p.terminate()

        plt.plot(waveform[:2*N])
        plt.title('Waveform')
        plt.show()

        file_name = "output.wav"
        signal_int16 = np.int16(waveform * 32767)
        write(file_name, sampling_freq, signal_int16)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DrawingPad()
    ex.showMaximized()  
    sys.exit(app.exec_())
