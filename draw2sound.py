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

        twelve_edo_action = QAction("12 edo", self)
        twelve_edo_action.triggered.connect(self.add_12edo_preset)
        presets_menu.addAction(twelve_edo_action)

        eleven_edo_action = QAction("11 edo", self)
        eleven_edo_action.triggered.connect(self.add_11edo_preset)
        presets_menu.addAction(eleven_edo_action)

        ten_edo_action = QAction("10 edo", self)
        ten_edo_action.triggered.connect(self.add_10edo_preset)
        presets_menu.addAction(ten_edo_action)

        nine_edo_action = QAction("9 edo", self)
        nine_edo_action.triggered.connect(self.add_9edo_preset)
        presets_menu.addAction(nine_edo_action)

        eight_edo_action = QAction("8 edo", self)
        eight_edo_action.triggered.connect(self.add_8edo_preset)
        presets_menu.addAction(eight_edo_action)

        seven_edo_action = QAction("7 edo", self)
        seven_edo_action.triggered.connect(self.add_7edo_preset)
        presets_menu.addAction(seven_edo_action)

        six_edo_action = QAction("6 edo", self)
        six_edo_action.triggered.connect(self.add_6edo_preset)
        presets_menu.addAction(six_edo_action)

        five_edo_action = QAction("5 edo", self)
        five_edo_action.triggered.connect(self.add_5edo_preset)
        presets_menu.addAction(five_edo_action)

        four_edo_action = QAction("4 edo", self)
        four_edo_action.triggered.connect(self.add_4edo_preset)
        presets_menu.addAction(four_edo_action)

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
        if self.tab_widget.currentIndex() == 1:
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
        self.frequency_canvas.position = []
        
        num_terms = 1000
        fundamental_freq = 100
        for n in range(1, num_terms + 1):
            if n % 2 == 1:
                amplitude = 4 / (n * np.pi)
                frequency = n * fundamental_freq
                self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

        self.frequency_canvas.update()
        self.frequency_canvas.chooseSound()


    def add_triangle_preset(self):
        
        self.frequency_canvas.position = []

        num_terms = 1000
        fundamental_freq = 100
        for n in range(1, num_terms + 1):
            if n % 2 == 1:
                amplitude = (8 / (np.pi**2 * (n**2))) * (-1)**((n-1)/2)
                frequency = n * fundamental_freq
                self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

        self.frequency_canvas.update()
        self.frequency_canvas.chooseSound()

    def add_saw_preset(self):
        self.frequency_canvas.position = []

        num_terms = 1000
        fundamental_freq = 100
        for n in range(1, num_terms + 1):
            amplitude = 1 / n  
            frequency = n * fundamental_freq
            self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

        self.frequency_canvas.update()
        self.frequency_canvas.chooseSound()

    def add_4edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([4, 7, 8, 10, 10, 11, 12, 13, 14, 14, 15])
        n = 4
        self.xedo_append_coefficients(p, n)   

    def add_5edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([5, 8, 10, 12, 13, 14, 15, 16, 17, 17, 18])
        n = 5
        self.xedo_append_coefficients(p, n)   

    def add_6edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([6, 10, 12, 14, 16, 17, 18, 19, 20, 21, 22])
        n = 6
        self.xedo_append_coefficients(p, n)   
    
    def add_7edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([7, 11, 14, 16, 18, 20, 21, 22, 23, 24, 25])
        n = 7
        self.xedo_append_coefficients(p, n)

    def add_8edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([8, 13, 16, 19, 21, 22, 24, 25, 27, 28, 29])
        n = 8
        self.xedo_append_coefficients(p, n)
    
    def add_9edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([9, 14, 18, 21, 23, 25, 27, 29, 30, 31, 32])
        n = 9
        self.xedo_append_coefficients(p, n)

    def add_10edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([10, 16, 20, 23, 26, 28, 30, 32, 33, 35, 36])
        n = 10
        self.xedo_append_coefficients(p, n)

    def add_11edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([11, 17, 22, 26, 28, 31, 33, 35, 37, 38, 39])
        n = 11
        self.xedo_append_coefficients(p, n)
    
    def add_12edo_preset(self):
        self.frequency_canvas.position = []
        p = np.array([0, 12, 19, 24, 28, 31, 34, 36, 38, 40, 42, 43])
        n = 12
        self.xedo_append_coefficients(p, n)
    
    def xedo_append_coefficients(self, p, n):
        a = 2**(1/n)
        LowerToneFrequency = 100
        PartialFrequencies = LowerToneFrequency * np.power(a, p)
        PartialAmplitudes = np.power(0.9, np.arange(1, 13))
        data_points = combined_list = list(zip(PartialFrequencies, PartialAmplitudes))
        self.append_coefficients(data_points)
        self.frequency_canvas.chooseSound()

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
