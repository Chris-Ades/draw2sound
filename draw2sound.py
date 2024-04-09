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

from d2s_synth import Synth

class Draw2SoundGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('draw2sound')
        self.setGeometry(100, 100, 600, 400)
        self.screen = QDesktopWidget().screenGeometry()
        self.screen_width, self.screen_height = self.screen.width(), self.screen.height()

        self.createTabs()

    def createTabs(self):
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Set style sheet for larger tabs
        self.tab_widget.setStyleSheet("QTabBar::tab { height: 40px; width: 150px; }")

        # Create tabs
        self.tab1 = QWidget()
        self.tab2 = QWidget()

        # Add tabs to tab widget
        self.tab_widget.addTab(self.tab1, "Time Canvas")
        self.tab_widget.addTab(self.tab2, "Frequency Canvas")

        # Populate Tab 1
        layout1 = QVBoxLayout()
        self.time_canvas = Canvas(self, 'time')
        layout1.addWidget(self.time_canvas)
        self.tab1.setLayout(layout1)

        # Populate Tab 2
        layout2 = QVBoxLayout()
        label2 = QLabel("This is Tab 2")
        layout2.addWidget(label2)
        self.tab2.setLayout(layout2)

        self.tab_widget.currentChanged.connect(self.tab_changed)

    def closeEvent(self, event):
        if (self.time_canvas.pyo_server.getIsBooted):
            self.time_canvas.pyo_server.shutdown()
            #also shut down all Scope, Spectrum, Keyboard windows
        
        print("shutting down")
        event.accept()

    def tab_changed(self, index):
        # Get the index of the currently selected tab
        current_tab_index = self.tab_widget.currentIndex()
        print("Tab changed to:", current_tab_index)

class Canvas(QWidget):
    def __init__(self, parent, domain):
        super().__init__(parent)
        self.domain = domain # time or frequency

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

        self.pyo_server = Server()
        self.pyo_server.setMidiInputDevice(99)
        self.pyo_server.boot()
        self.notes = Notein(poly=16, scale=1, first=0, last=127, channel=0, mul=1)

        # Play sound button
        move_x = parent.screen_width
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

        if self.pyo_server.getIsStarted():
            self.a.stop()
            self.pyo_server.stop()

    def add_point(self, pos):
        self.x_values.append(pos.x() - self.width() / 2)
        self.y_values.append(pos.y() - self.height() / 2)

    def chooseSound(self):
        # Handle time domain sound maker
        if self.domain == "time":
            if (self.y_values == []):
                return
            y = np.array(self.y_values)
            max_norm = np.max(np.abs(y))
            wave = y / max_norm
            waveform = y / max_norm
            N = len(wave)
            duration = 5 # seconds
            fund_freq = int(220)
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
            signal_int16 = np.int16(waveform * 32767)
            write(self.file_name, sampling_freq, signal_int16)

            self.pyo_server.start()
            self.start_synth(fund_freq)

            self.chooseSoundButton.setEnabled(False)
            self.scopeButton.setEnabled(True)

            self.spectrumButton.setEnabled(True)
            self.keyboardButton.setEnabled(True)    

    def start_synth(self, fund_freq):
        file_path = os.getcwd() + "/" + self.file_name
        if (os.path.exists(file_path) == False):
            self.message_box(file_path + " DNE")
            return

        self.a = Synth(file_path, fund_freq, self.notes)
        self.a.out()

    def show_scope(self):
        #checks if there is a Scope window already open
        self.sc = Scope(self.a.sig())
        self.sc.view(title="Scope", wxnoserver=True)
    
    def show_spectrum(self):
        #checks if there is a Scope window already open
        self.sp = Spectrum(self.a.sig())
        #self.sp.setSize(4096)
        #self.sp.setFscaling(True)
        self.sp.view(title="Spectrum", wxnoserver=True)
    
    def show_keyboard(self):
        #checks if there is a Scope window already open
        self.notes.keyboard(title="Keyboard", wxnoserver=True)

    def message_box(self, message):
        msg_box = QMessageBox()
        msg_box.setText(message)
        msg_box.exec_()

    # def close_window(self, window_title):
    #     system = platform.system()
    #     if system == 'Windows':
    #         os.system(f'taskkill /f /im "{window_title}"')
    #     elif system == 'Darwin':  # macOS
    #         os.system(f"osascript -e 'tell application \"System Events\" to delete (every window whose name is \"{window_title}\")'")
    #     elif system == 'Linux':
    #         subprocess.run(['xdotool', 'search', '--name', window_title, 'windowkill'])
    #     else:
    #         print("Unsupported operating system")

def main():
    app = QApplication(sys.argv)
    ex = Draw2SoundGUI()
    ex.show()
    #ex.showFullScreen()
    ex.showMaximized()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
