import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QColorDialog, QVBoxLayout, QWidget, QLabel, QPushButton, QMessageBox, QDesktopWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt5.QtCore import Qt
import numpy as np
import pyaudio
from astropy.convolution import convolve, Box1DKernel
from scipy.io.wavfile import write
from pyo import *

import platform
import subprocess
import os

from d2s_synth import D2S_synth

import matplotlib.pyplot as plt

import time

class Draw2SoundGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('draw2sound')
        self.setGeometry(100, 100, 600, 400)
        self.screen = QDesktopWidget().screenGeometry()
        self.screen_width, self.screen_height = self.screen.width(), self.screen.height()

        self.pyo_server = Server()
        self.pyo_server.setMidiInputDevice(99)
        self.pyo_server.boot()
        self.notes = Notein(poly=16, scale=1, first=0, last=127, channel=0, mul=1)

        self.createTabs()

    def createTabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        self.tab_widget.setStyleSheet("QTabBar::tab { height: 40px; width: 150px; }")

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

    def closeEvent(self, event):
        if (self.time_canvas.pyo_server.getIsBooted):
            self.time_canvas.pyo_server.shutdown()
            #also shut down all Scope, Spectrum, Keyboard windows
        
        print("shutting down")
        event.accept()

    # def tab_changed(self, index):
    #     # Get the index of the currently selected tab
    #     current_tab_index = self.tab_widget.currentIndex()
    #     print("Tab changed to:", current_tab_index)

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
        self.lastPoint = None
        self.x_values = []
        self.y_values = []
        self.mouse_position_label = QLabel(self)
        self.mouse_position_label.move(10, 10)  
        self.mouse_position_label.setText("Mouse Position: (0, 0)")

        self.file_name = "output.wav" # sample name

        self.pyo_server = parent.pyo_server
        self.notes = parent.notes
        self.max_freq = 4096 # maximum frequency one can draw in frequency mode

        # Play sound button
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
            painter.drawLine(0, self.height() // 2, self.width(), self.height() // 2)
            painter.drawLine(self.width() // 2, 0, self.width() // 2, self.height())
        
        if self.domain == "frequency":
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
                
            centerLineThickness = 4  
            painter.setPen(QPen(Qt.gray, centerLineThickness, Qt.SolidLine))
            painter.drawLine(0, self.height(), self.width(), self.height())
            painter.drawLine(0, 0, 0, self.height()) 

    def mousePressEvent(self, event):
        if self.drawingEnabled and event.button() == Qt.LeftButton:
            self.lastPoint = event.pos()
            self.path.moveTo(self.lastPoint)
            self.add_point(event.pos())

    def mouseMoveEvent(self, event):
        if self.domain == "time":
            x = event.x() - self.width() / 2
            y = event.y() - self.height() / 2
        if self.domain == "frequency":
            x = int(round(event.x() * self.max_freq / self.width(), 0))
            y = self.height() - event.y()
        self.mouse_position_label.setText(f"({x}, {y})")
        if self.drawingEnabled and event.buttons() & Qt.LeftButton:
            if event.pos().x() > self.lastPoint.x():
                self.path.lineTo(event.pos())
                self.update()
                self.lastPoint = event.pos()
                self.add_point(event.pos())

    def mouseReleaseEvent(self, event):
        if self.drawingEnabled and event.button() == Qt.LeftButton:
            self.chooseSoundButton.setEnabled(True)
            self.path.lineTo(event.pos())
            self.update()
            self.drawingEnabled = False 

    def clearCanvas(self):
        self.path = QPainterPath()
        self.update()
        self.drawingEnabled = True
        self.x_values = []
        self.y_values = []

        self.chooseSoundButton.setEnabled(False)
        self.scopeButton.setEnabled(False)
        self.spectrumButton.setEnabled(False)
        self.keyboardButton.setEnabled(False)

        if self.domain == "time":
            self.parent.tab_widget.setTabEnabled(1, True)
        
        if self.domain == "frequency":
            self.parent.tab_widget.setTabEnabled(0, True)

        if self.pyo_server.getIsStarted():
            self.a.stop()
            self.pyo_server.stop()

    def add_point(self, pos):

        if self.domain == "time":
            self.x_values.append(pos.x() - self.width() / 2)
            self.y_values.append(pos.y() - self.height() / 2)

        if self.domain == "frequency":
            self.x_values.append(int(round(pos.x() * self.max_freq / self.width(), 0)))
            self.y_values.append(self.height() - pos.y())

    def chooseSound(self):
        if (self.y_values == []):
            return

        if self.domain == "time":
            self.parent.tab_widget.setTabEnabled(1, False)
            # interpolate values like you did so you can increase sampling frequency
            # scale time domain and add number markers
            y = np.array(self.y_values)
            max_norm = np.max(np.abs(y))
            wave = y / max_norm
            waveform = y / max_norm
            N = len(wave)
            print(N)
            duration = 5 # seconds
            fund_freq = int(220)
            sampling_freq = N*fund_freq 
            amplitude = 1

            for i in range(duration):
                for j in range(fund_freq):
                    waveform = np.concatenate((waveform, wave))
            waveform = -1 * amplitude * waveform

            w = 10 # Points to avg in the smoothing process
            waveform = convolve(waveform, Box1DKernel(w))
            signal_int16 = np.int16(waveform * 32767)
            write(self.file_name, sampling_freq, signal_int16)
            
            #self.show_fft(wave, sampling_freq)

            self.pyo_server.start()
            self.start_synth(fund_freq, loop=True)
            self.chooseSoundButton.setEnabled(False)
            self.scopeButton.setEnabled(True)
            self.spectrumButton.setEnabled(True)
            self.keyboardButton.setEnabled(True)    

        if self.domain == "frequency":
            self.parent.tab_widget.setTabEnabled(0, False)
            x = np.array(self.x_values)
            y = np.array(self.y_values)
            y[y < 0] = 0
            max_norm = np.max(y)
            y = y / max_norm

            x_new = np.arange(x[0], x[-1]+1)
            y_new = np.interp(x_new, x, y)
            first_elem = x[0]
            last_elem = x[-1]
            
            amplitudes = y_new
            if first_elem != 0:
                pad_left = np.zeros(first_elem - 1)
                amplitudes = np.concatenate((pad_left, y_new))

            if last_elem != self.max_freq:
                pad_right = np.zeros(self.max_freq - last_elem)
                amplitudes = np.concatenate((amplitudes, pad_right))

            frequencies = np.arange(1, self.max_freq + 1)

            #######################################################################
            N = 44100
            period = 2*np.pi 
            sampling_freq = N
            t = np.linspace(0, period, N, endpoint=False)

            waveform = np.zeros_like(t)

            start_time = time.time()
            for i in range(self.max_freq):
                if amplitudes[i] != 0:
                    waveform = waveform + (amplitudes[i]*np.sin(frequencies[i] * t))
            end_time = time.time()

            fund_freq = frequencies[np.argmax(amplitudes)]

            elapsed_time = end_time - start_time
            print(f"Elapsed time for {10000} iterations: {elapsed_time} seconds")

            duration = 5
            waveform = np.tile(waveform, duration) 
            waveform = waveform / np.max(waveform)
            # Plot the sine wave
            plt.plot(waveform)
            plt.xlabel('Time')
            plt.ylabel('Amplitude')
            plt.title('One Period of a Sine Wave')
            plt.grid(True)
            plt.show()
            
            ###########################################################################
            signal_int16 = np.int16(waveform * 32767)
            write(self.file_name, sampling_freq, signal_int16)
            #self.show_fft(waveform, sampling_freq)

            self.pyo_server.start()
            self.start_synth(fund_freq, loop=True)
            self.chooseSoundButton.setEnabled(False)
            self.scopeButton.setEnabled(True)
            self.spectrumButton.setEnabled(True)
            self.keyboardButton.setEnabled(True)   
            

    def start_synth(self, fund_freq, loop):
        file_path = os.getcwd() + "/" + self.file_name
        if (os.path.exists(file_path) == False):
            self.message_box(file_path + " DNE")
            return

        self.a = D2S_synth(file_path, fund_freq, self.notes, loop)
        self.a.out()

        # self.sc = Scope(self.a.sig())
        # self.sp = Spectrum(self.a.sig())

    def show_scope(self):
        #self.sc.view(title="Scope", wxnoserver=True)
        return
    
    def show_spectrum(self):
        #self.sp.setSize(4096)
        #self.sp.setFscaling(True)
        #self.sp.view(title="Spectrum", wxnoserver=True)
        return
    
    def show_keyboard(self):
        #checks if there is a Scope window already open
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

def main():
    app = QApplication(sys.argv)
    ex = Draw2SoundGUI()
    ex.show()
    #ex.showFullScreen()
    ex.showMaximized()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
