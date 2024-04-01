import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QColorDialog, QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt5.QtCore import Qt
import numpy as np
#import matplotlib.pyplot as plt
import pyaudio
from astropy.convolution import convolve, Box1DKernel
from scipy.io.wavfile import write
from pyo import *

class Draw2SoundGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    # Initialize UI
    def initUI(self):
        self.mode = 'time' # will change to 'frequency' or 'XY'
        self.drawn = False # if true then change 

        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle('draw2sound')
        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self.createButtons()
        self.show()

    def createButtons(self):
        move_x = 100 # adjust x position of buttons

        # Clear Sound button
        clearButton = QPushButton('Clear', self)
        clearButton.clicked.connect(self.canvas.clearCanvas)
        clearButton.setGeometry(10+move_x, 10, 100, 30)
        clearButton.setStyleSheet("background-color: red;")

        # Play sound button
        chooseSoundButton = QPushButton('Choose Sound', self)
        chooseSoundButton.clicked.connect(self.canvas.chooseSound)
        chooseSoundButton.setGeometry(120+move_x, 10, 100, 30)

        # Frequency Mode

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

    def chooseSound(self):
        x = self.x_values 
        y = np.array(self.y_values)

        max_norm = np.max(np.abs(y))
        wave = y / max_norm
        waveform = y / max_norm
        N = len(wave)
        fund_freq = int(220)
        duration = 5 # seconds
        sampling_freq = N*fund_freq 
        amplitude = 1

        for i in range(duration):
            for j in range(fund_freq):
                waveform = np.concatenate((waveform, wave))

        waveform = -1 * amplitude * waveform

        # Smooth out the signal
        w = 10 # Points to avg in the smoothing process
        waveform = convolve(waveform, Box1DKernel(w)) # boxcar smoothing

        # write waveform to a wav file
        file_name = "output.wav"
        signal_int16 = np.int16(waveform * 32767)
        write(file_name, sampling_freq, signal_int16)

        ####################_make below its own function_#############################
        # Handle MIDI input using PYO
        file_path = os.getcwd() + "/" + file_name

        if os.path.exists(file_path):
            print("The file exists.")
        else:
            print("The file does not exist.")

        s = Server()
        s.setMidiInputDevice(99)  # Open all input devices.
        s.boot().start()

        notes = Notein(scale=1) # Gets MIDI note info
        notes.keyboard() # Show keyboard if no MIDI hardware

        vol = Midictl(ctlnumber=88, minscale=0, maxscale=1, init=0.2) # Volume ctlr from midi

        env = MidiAdsr(notes["velocity"], attack=0.005, decay=0.1, sustain=0.7, release=0.5, mul=vol) # ASDR

        transpo = Sig(Bendin(brange=12, scale=1)) # Handle pitch bend

        soundR = SfPlayer(file_path, speed=notes["pitch"]*transpo/fund_freq, loop=True, offset=0, interp=2, mul=env, add=0).out(0)
        soundL = SfPlayer(file_path, speed=notes["pitch"]/fund_freq, loop=True, offset=0, interp=2, mul=env, add=0).out(1)

        sc = Scope(soundR + soundL) # Show scope
        sp = Spectrum(soundR + soundL) # Show spectrum

        s.gui()


def main():
    app = QApplication(sys.argv)
    ex = Draw2SoundGUI()
    ex.showMaximized()  
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
