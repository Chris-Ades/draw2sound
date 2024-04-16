import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QColorDialog, QVBoxLayout, QWidget, QLabel, QPushButton, QMessageBox, QDesktopWidget, QTabWidget
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
        self.pyo_server.boot().start()
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
        self.tab_widget.setStyleSheet("QTabBar::tab { height: 40px; width: 150px; }")

        self.tab1 = QWidget()
        self.tab2 = QWidget()

        self.tab_widget.addTab(self.tab1, "Time Mode")
        self.tab_widget.addTab(self.tab2, "Frequency Mode")

        layout1 = QVBoxLayout()
        self.time_canvas = Canvas(self, 'time')
        layout1.addWidget(self.time_canvas)
        self.tab1.setLayout(layout1)

        layout2 = QVBoxLayout()
        self.frequency_canvas = Canvas(self, 'frequency')
        layout2.addWidget(self.frequency_canvas)
        self.tab2.setLayout(layout2)
    
    def createMenu(self):
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

        # ten_edo_action = QAction("10 edo", self)
        # ten_edo_action.triggered.connect(self.add_10edo_preset)
        # presets_menu.addAction(ten_edo_action)

        if self.tab_widget.currentIndex() == 1:
            pass

    def add_sine_preset(self):
        if self.tab_widget.currentIndex() == 1: # for frequency mode
            self.frequency_canvas.position = []
            
            fundamental_freq = 100
            amplitude = 1
            self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(fundamental_freq), self.frequency_canvas.y_transform_inverse(amplitude)))
            
            self.frequency_canvas.update()
            self.frequency_canvas.chooseSoundButton.setEnabled(True)

    def add_square_preset(self):
        if self.tab_widget.currentIndex() == 1: # for frequency mode
            self.frequency_canvas.position = []
            
            num_terms = 400
            fundamental_freq = 100
            for n in range(1, num_terms + 1):
                if n % 2 == 1:
                    amplitude = 4 / (n * np.pi)
                    frequency = n * fundamental_freq
                    self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

            self.frequency_canvas.update()
            self.frequency_canvas.chooseSoundButton.setEnabled(True)

    def add_triangle_preset(self):
        if self.tab_widget.currentIndex() == 1:
            self.frequency_canvas.position = []

            num_terms = 400
            fundamental_freq = 100
            for n in range(1, num_terms + 1):
                if n % 2 == 1:
                    amplitude = (8 / (np.pi**2 * (n**2))) * (-1)**((n-1)/2)
                    frequency = n * fundamental_freq
                    self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

            self.frequency_canvas.update()
            self.frequency_canvas.chooseSoundButton.setEnabled(True)

    def add_saw_preset(self):
        if self.tab_widget.currentIndex() == 1:
            self.frequency_canvas.position = []

            num_terms = 400
            fundamental_freq = 100
            for n in range(1, num_terms + 1):
                amplitude = 1 / n  
                frequency = n * fundamental_freq
                self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

            self.frequency_canvas.update()
            self.frequency_canvas.chooseSoundButton.setEnabled(True)

    def add_10edo_preset(self):
        if self.tab_widget.currentIndex() == 1:
            self.frequency_canvas.position = []
 
            b = 2**(1/10)
            f = 100
            data_points = [(f, 1), (f*b**10, 1/2), (f*b**17, 1/3), (f*b**20, 1/4), (f*b**25, 1/5), (f*b**28, 1/6), (f*b**30, 1/7)]
            for point in data_points:
                frequency, amplitude = point
                self.frequency_canvas.position.append((self.frequency_canvas.x_transform_inverse(frequency), self.frequency_canvas.y_transform_inverse(amplitude)))

            self.frequency_canvas.update()
            self.frequency_canvas.chooseSoundButton.setEnabled(True)

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
