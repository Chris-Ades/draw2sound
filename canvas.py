import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QColorDialog, QVBoxLayout, QWidget, QLabel, QPushButton, QMessageBox, QDesktopWidget, QTabWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath, QFont
from PyQt5.QtCore import Qt, QPoint
import numpy as np
import pyaudio
from astropy.convolution import convolve, Box1DKernel
from scipy.io.wavfile import write
from scipy.interpolate import interp1d
from pyo import *

import platform
import subprocess
import os

from d2s_synth import D2S_synth
import matplotlib.pyplot as plt
import time


class Canvas(QWidget):
    def __init__(self, parent, domain):
        super().__init__(parent)
        self.domain = domain # time or frequency
        self.parent = parent

        self.setGeometry(0, 0, 800, 600)
        self.setMouseTracking(True)
        self.drawingEnabled = True 
        self.pen = QPen(Qt.black, 2)
        self.path = QPainterPath()

        if self.domain == 'time':
            self.lastPoint = None
            self.x_values = []
            self.y_values = []

        if self.domain == 'frequency':
            self.position = []
            self.current_drag_point = None
            self.drag_offset = None
            self.diameter = 8
            self.mag_norm = 0.5*self.height() # scale to screen size
            self.max_x = 1500 
            self.x_divider = 4/3

        self.mouse_position_label = QLabel(self)
        self.mouse_position_label.move(10, 10)  
        self.mouse_position_label.setText("(0, 0)                       ")

        self.pyo_server = parent.pyo_server
        self.notes = parent.notes
        self.file_name = parent.file_name
        self.file_path = parent.file_path
        self.synth = parent.synth
        self.scope = parent.scope
        self.spectrum = parent.spectrum

        move_x = self.width()
        self.chooseSoundButton = QPushButton('Choose Sound', self)
        self.chooseSoundButton.clicked.connect(self.chooseSound)
        self.chooseSoundButton.setGeometry(move_x-260, 0, 100, 30)
        self.chooseSoundButton.setEnabled(False)

        self.clearButton = QPushButton('Clear', self)
        self.clearButton.clicked.connect(self.clearCanvas)
        self.clearButton.setGeometry(move_x-130, 0, 100, 30)
        self.clearButton.setStyleSheet("background-color: red;")

        self.scopeButton = QPushButton('Scope', self)
        self.scopeButton.clicked.connect(self.show_scope)
        self.scopeButton.setGeometry(move_x-390, 0, 100, 30)
        self.scopeButton.setEnabled(False)

        self.spectrumButton = QPushButton('Spectrum', self)
        self.spectrumButton.clicked.connect(self.show_spectrum)
        self.spectrumButton.setGeometry(move_x-520, 0, 100, 30)
        self.spectrumButton.setEnabled(False)

        self.keyboardButton = QPushButton('Keyboard', self)
        self.keyboardButton.clicked.connect(self.show_keyboard)
        self.keyboardButton.setGeometry(move_x-650, 0, 100, 30)
        self.keyboardButton.setEnabled(False)

    def paintEvent(self, event):
        if self.domain == "time":
            painter = QPainter(self)
            painter.setPen(self.pen)
            painter.drawPath(self.path)
            
            gridSize = 40
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
            painter.setPen(QPen(Qt.gray, centerLineThickness, Qt.SolidLine))
            painter.drawLine(0, self.height() // 2, self.width(), self.height() // 2)
            painter.drawLine(self.width() // 2, 0, self.width() // 2, self.height())
            
            painter.setFont(QFont("Arial", 12))
            painter.setPen(self.pen)
            # painter.drawText(self.width() // 2, self.height() // 2, "0")
            # painter.drawText(0.05*self.width(), self.height() // 2, "-T/2")
            # painter.drawText(self.width() - 0.05*self.width(), self.height() // 2, "T/2")

        if self.domain == "frequency":
            painter = QPainter(self)
            painter.setFont(QFont("Arial", 12))
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
            painter.setPen(QPen(Qt.gray, centerLineThickness, Qt.SolidLine))
            painter.drawLine(0, self.height()/self.x_divider, self.width(), self.height()/self.x_divider)
            centerLineThickness = 4  
            painter.setPen(QPen(Qt.gray, centerLineThickness, Qt.SolidLine))
            painter.drawLine(0, 0, 0, self.height()) 
            
            painter.setPen(self.pen)
            for point in self.position:
                x, y = point
                painter.setBrush(Qt.black)
                painter.drawEllipse(QPoint(x, y), self.diameter, self.diameter)
                text_position = QPoint(x, y - 30)
                painter.drawText(text_position, f"({self.x_transform(x)}, {self.y_transform(y)})")

                painter.setPen(QPen(Qt.black, 2, Qt.SolidLine))
                painter.drawLine(x, y, x, self.height()/self.x_divider)

    def mousePressEvent(self, event):
        if self.domain == "time":
            if self.drawingEnabled and event.button() == Qt.LeftButton:
                self.lastPoint = event.pos()
                self.path.moveTo(self.lastPoint)
                self.add_point(event.pos())

        if self.domain == "frequency":
            for i, point in enumerate(self.position):
                if abs(point[0] - event.x()) <= self.diameter and abs(point[1] - event.y()) <= self.diameter:
                    self.current_drag_point = i
                    self.drag_offset = QPoint(event.pos() - QPoint(point[0], point[1]))
                    return

            self.position.append((event.x(), event.y()))
            self.update()
            self.chooseSoundButton.setEnabled(True)

    def mouseMoveEvent(self, event):
        if self.domain == "time":
            x = event.x() - self.width() / 2
            y = event.y() - self.height() / 2
            self.mouse_position_label.setText(f"({x}, {y})")
            if self.drawingEnabled and event.buttons() & Qt.LeftButton:
                if event.pos().x() > self.lastPoint.x():
                    self.path.lineTo(event.pos())
                    self.update()
                    self.lastPoint = event.pos()
                    self.add_point(event.pos())

        if self.domain == "frequency":
            x = self.x_transform(event.x())
            y = self.y_transform(event.y())
            self.mouse_position_label.setText(f"({x}, {y})")

            if self.current_drag_point is not None:
                self.position[self.current_drag_point] = (event.x() - self.drag_offset.x(),
                                                            event.y() - self.drag_offset.y())
                self.update()

    def mouseReleaseEvent(self, event):
        if self.domain == "time":
            if self.drawingEnabled and event.button() == Qt.LeftButton:
                self.chooseSoundButton.setEnabled(True)
                self.path.lineTo(event.pos())
                self.update()
                self.drawingEnabled = False

        if self.domain == "frequency":
            if event.button() == Qt.LeftButton:
                self.current_drag_point = None

    def mouseDoubleClickEvent(self, event):
        if self.domain == "frequency":
            for i, point in enumerate(self.position):
                if abs(point[0] - event.x()) <= self.diameter and abs(point[1] - event.y()) <= self.diameter:
                    del self.position[i]
                    self.update()
                    if self.position == []:
                        self.chooseSoundButton.setEnabled(False)
                    return

    def clearCanvas(self):
        self.chooseSoundButton.setEnabled(False)
        self.scopeButton.setEnabled(False)
        self.spectrumButton.setEnabled(False)
        self.keyboardButton.setEnabled(False)

        if self.domain == "time":
            self.path = QPainterPath()
            self.update()
            self.drawingEnabled = True
            self.x_values = []
            self.y_values = []
            self.parent.tab_widget.setTabEnabled(1, True)

        if self.domain == "frequency":
            self.position = []
            self.parent.tab_widget.setTabEnabled(0, True)
            self.update()

        self.synth.stop()
        

    def add_point(self, pos):
        if self.domain == "time":
            self.x_values.append(pos.x() - self.width() / 2)
            self.y_values.append(pos.y() - self.height() / 2)

    def chooseSound(self):
        if self.domain == "time":
            if (self.y_values == []):
                return
            self.parent.tab_widget.setTabEnabled(1, False)
            # interpolate values like you did so you can increase sampling frequency
            # scale time domain and add number markers
            x = np.array(self.x_values)
            y = np.array(self.y_values)
            
            fund_freq = int(220)
            sampling_freq = int(44000)
            N = int(sampling_freq / fund_freq)

            interp_func = interp1d(x, y, kind='linear')

            x_resampled = np.linspace(x[0], x[-1], N)
            y_resampled = interp_func(x_resampled)
            wave = y_resampled / np.max(np.abs(y_resampled))

            duration = 5
            waveform = -1*np.tile(wave, fund_freq*duration) 

            w = 2 # Points to avg in the smoothing process
            waveform = convolve(waveform, Box1DKernel(w))

            signal_int16 = np.int16(waveform * 32767)
            write(self.file_name, sampling_freq, signal_int16)
            #self.show_fft(waveform, sampling_freq)

            self.start_synth(fund_freq)
            self.chooseSoundButton.setEnabled(False)
            self.scopeButton.setEnabled(True)
            self.spectrumButton.setEnabled(True)
            self.keyboardButton.setEnabled(True)    

        if self.domain == "frequency":
            self.parent.tab_widget.setTabEnabled(0, False)

            data_points = [(self.x_transform(x), self.y_transform(y)) for x, y in self.position]

            N = 44100
            period = 2*np.pi 
            sampling_freq = N
            t = np.linspace(0, period, N, endpoint=False) # this is one second of time

            waveform = np.zeros_like(t)

            for point in data_points:
                freq, magnitude = point
                if magnitude != 0:
                    waveform = waveform + (magnitude*np.sin(freq * t))

            fund_freq = max(data_points, key=lambda x: x[1])[0]

            duration = 5
            waveform = np.tile(waveform, duration) 
            waveform = waveform / np.max(waveform)
            
            signal_int16 = np.int16(waveform * 32767)
            write(self.file_name, sampling_freq, signal_int16)
            #self.show_fft(waveform, sampling_freq)
            
            self.start_synth(fund_freq)
            self.chooseSoundButton.setEnabled(False)
            self.scopeButton.setEnabled(True)
            self.spectrumButton.setEnabled(True)
            self.keyboardButton.setEnabled(True)   

    def start_synth(self, fund_freq):
        self.synth.setFundFreq(fund_freq)
        self.synth.setPath(self.file_path)
        self.synth.start()
        self.synth.out()

    def show_scope(self):
        self.scope.view(title="Scope", wxnoserver=True)
    
    def show_spectrum(self):
        self.spectrum.view(title="Spectrum", wxnoserver=True)
    
    def show_keyboard(self):
        self.notes.keyboard(title="Keyboard", wxnoserver=True)
    
    def show_fft(self, waveform, sampling_freq):
        fft_output = np.fft.fft(waveform)
        frequencies = np.fft.fftfreq(len(fft_output), 1/sampling_freq)
        positive_frequencies = frequencies[:len(frequencies)//2]
        fft_output_positive = fft_output[:len(fft_output)//2]
        plt.figure(figsize=(8, 4))
        plt.plot(positive_frequencies, np.abs(fft_output_positive))
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title('FFT of Waveform (Positive Frequencies)')
        plt.grid(True)
        plt.show()

    """ 
    Transformation from pyqt5 gui coordinate system to frequency domain coordinates
    """
    def x_transform(self, x):

        return int(round(x * self.max_x / self.width(), 0))
    
    def x_transform_inverse(self, x):
        return int(round((x * self.width() / self.max_x)))

    def y_transform(self, y):
        return round((self.height()/self.x_divider  - y)/self.mag_norm, 3)

    def y_transform_inverse(self, y):
        return int(round(self.height()/self.x_divider  - (y * self.mag_norm)))