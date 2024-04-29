import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QColorDialog, QVBoxLayout, QWidget, QLabel, QPushButton, QMessageBox, QDesktopWidget, QTabWidget, QHBoxLayout
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath, QFont
from PyQt5.QtCore import Qt, QPoint
import numpy as np
import pyaudio
from astropy.convolution import convolve, Box1DKernel
from scipy.io.wavfile import write
from pyo import *

import platform
import subprocess
import os
import matplotlib.pyplot as plt
import time

from d2s_synth import D2S_synth
from canvas import Canvas

class Draw2SoundGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('draw2sound')
        self.setGeometry(100, 100, 600, 400)
        self.screen = QDesktopWidget().screenGeometry()
        self.screen_width, self.screen_height = self.screen.width(), self.screen.height()

        self.startAudioServer()
        self.createTabs()
        self.createMenu()

        #self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnBottomHint)
    def startAudioServer(self):
        self.pyo_server = Server()
        self.pyo_server.setMidiInputDevice(99)
        self.pyo_server.boot()
        self.pyo_server.start()
        self.notes = Notein(poly=16, scale=1, first=0, last=127, channel=0, mul=1)
        self.file_name = "output.wav"
        self.file_path = os.getcwd() + "/" + self.file_name
        if (os.path.exists(self.file_path) == False):
            waveform = np.zeroes(44100)
            signal_int16 = np.int16(waveform * 32767)
            write(self.file_name, 44100, signal_int16)
        
        self.synth = D2S_synth(220, self.notes, self.file_path)

        self.scope = Scope(self.synth.sig())
        self.scope.setGain(4.3)

        self.spectrum = Spectrum(self.synth.sig())
        self.spectrum.setSize(4096)
        self.spectrum.setFscaling(True)
        

    def createTabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        width = str(self.screen_width // 9)
        self.tab_widget.setStyleSheet("QTabBar::tab { height: 35px; width: " + width + "px; }")

        self.tab1 = QWidget()
        self.tab2 = QWidget()

        self.tab_widget.addTab(self.tab1, "Time Canvas")
        self.tab_widget.addTab(self.tab2, "Frequency Canvas")

        layout1 = QVBoxLayout()
        self.time_canvas = Canvas(self, 'time')
        layout1.addWidget(self.time_canvas)
        self.tab1.setLayout(layout1)

        layout2 = QVBoxLayout()
        self.frequency_canvas = Canvas(self, 'frequency')
        layout2.addWidget(self.frequency_canvas)
        self.tab2.setLayout(layout2)
    
    def createMenu(self):
        height = 35
        self.menuBar().setFixedHeight(height)

        presets_menu = self.menuBar().addMenu("Presets")
        font = QFont()
        font.setPointSize(14)
        presets_menu.setFont(font)

        sine_action = QAction("Sine", self)
        sine_action.triggered.connect(self.add_sine_preset)
        presets_menu.addAction(sine_action)

        square_action = QAction("Square", self)
        square_action.triggered.connect(self.add_square_preset)
        presets_menu.addAction(square_action)

        triangle_action = QAction("Triangle", self)
        triangle_action.triggered.connect(self.add_triangle_preset)
        presets_menu.addAction(triangle_action)

        saw_action = QAction("Saw", self)
        saw_action.triggered.connect(self.add_saw_preset)
        presets_menu.addAction(saw_action)

        ten_edo_action = QAction("10 edo", self)
        ten_edo_action.triggered.connect(self.add_10edo_preset)
        presets_menu.addAction(ten_edo_action)

        ###################################################
        width = self.screen_width//9

        scopeButton = QPushButton("Scope", self)
        scopeButton.clicked.connect(self.scopeButton_clicked)
        scopeButton.setFixedHeight(height-5)
        scopeButton.setFixedWidth(width)

        spectrumButton = QPushButton("Spectrum", self)
        spectrumButton.clicked.connect(self.spectrumButton_clicked)
        spectrumButton.setFixedHeight(height-5)
        spectrumButton.setFixedWidth(width)

        self.loadButton = QPushButton("Load Sound", self)
        self.loadButton.clicked.connect(self.loadButton_clicked)
        self.loadButton.setFixedHeight(height-5)
        self.loadButton.setFixedWidth(width)

        clearButton = QPushButton("Clear", self)
        clearButton.clicked.connect(self.clearButton_clicked)
        clearButton.setFixedHeight(height-5)
        clearButton.setFixedWidth(width)
        clearButton.setStyleSheet("background-color: red;")

        layout = QHBoxLayout()
        layout.addWidget(scopeButton)
        layout.addWidget(spectrumButton)
        layout.addWidget(self.loadButton)
        layout.addWidget(clearButton)
        widget = QWidget()
        widget.setLayout(layout)
        self.menuBar().setCornerWidget(widget)

    def loadButton_clicked(self):
        if self.tab_widget.currentIndex() == 0:
            self.time_canvas.chooseSound()
        else:
            self.frequency_canvas.chooseSound()

    def clearButton_clicked(self):
        if self.tab_widget.currentIndex() == 0:
            self.time_canvas.clearCanvas()
        else:
            self.frequency_canvas.clearCanvas()

        self.loadButton.setStyleSheet("")

    def scopeButton_clicked(self):
        self.scope.view(title="Scope", wxnoserver=True)

    def spectrumButton_clicked(self):
        self.spectrum.view(title="Spectrum", wxnoserver=True)

    def add_sine_preset(self):
        if self.tab_widget.currentIndex() == 1: # for frequency mode
            self.frequency_canvas.position = []
            
            fundamental_freq = 100
            amplitude = 1
            self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(fundamental_freq), self.frequency_canvas.y_transform_inverse(amplitude)))
            
            self.frequency_canvas.update()

        if self.tab_widget.currentIndex() == 0:
            self.time_canvas.clearCanvas()

            t = np.linspace(0, int(self.time_canvas.width()), int(self.time_canvas.width()))
            wave = 0.45*self.time_canvas.height()*np.sin((2*np.pi*t)) + self.time_canvas.height()//2 
            data = list(zip(t, wave))

            initial = True
            for pos in data:
                if initial == True:
                    self.time_canvas.path.moveTo(pos[0], pos[1])
                    initial = False
                else:
                    self.time_canvas.path.lineTo(pos[0], pos[1])
                self.time_canvas.update()

            self.time_canvas.drawingEnabled = False
            data = list(zip(t, wave - self.time_canvas.height()//2 ))
            self.time_canvas.x_values = [point[0] for point in data]
            self.time_canvas.y_values = [point[1] for point in data]

    def add_square_preset(self):
        if self.tab_widget.currentIndex() == 1: # for frequency mode
            self.frequency_canvas.position = []
            
            num_terms = 1000
            fundamental_freq = 100
            for n in range(1, num_terms + 1):
                if n % 2 == 1:
                    amplitude = 4 / (n * np.pi)
                    frequency = n * fundamental_freq
                    self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

            self.frequency_canvas.update()


    def add_triangle_preset(self):
        if self.tab_widget.currentIndex() == 1:
            self.frequency_canvas.position = []

            num_terms = 1000
            fundamental_freq = 100
            for n in range(1, num_terms + 1):
                if n % 2 == 1:
                    amplitude = (8 / (np.pi**2 * (n**2))) * (-1)**((n-1)/2)
                    frequency = n * fundamental_freq
                    self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

            self.frequency_canvas.update()

    def add_saw_preset(self):
        if self.tab_widget.currentIndex() == 1:
            self.frequency_canvas.position = []

            num_terms = 1000
            fundamental_freq = 100
            for n in range(1, num_terms + 1):
                amplitude = 1 / n  
                frequency = n * fundamental_freq
                self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

            self.frequency_canvas.update()

    def add_10edo_preset(self):
        if self.tab_widget.currentIndex() == 1:
            self.frequency_canvas.position = []
            b = 2**(1/10)
            f = 100
            data_points = [(f, 1), (f*b**10, 1/2), (f*b**17, 1/3), (f*b**20, 1/4), (f*b**25, 1/5), (f*b**28, 1/6), (f*b**30, 1/7)]
            self.append_coefficients(data_points)

    def append_coefficients(self, data_points):
            for point in data_points:
                frequency, amplitude = point
                self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))
            self.frequency_canvas.update()

    def closeEvent(self, event):
        if (self.time_canvas.pyo_server.getIsBooted):
            self.time_canvas.pyo_server.shutdown()
        print("shutting down")
        sys.exit()

def main():
    app = QApplication(sys.argv)
    app.setDoubleClickInterval(200)
    ex = Draw2SoundGUI()
    ex.show()
    #ex.showFullScreen()
    ex.showMaximized()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
