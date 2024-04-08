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
        # Add TimeCanvas widget to tab1
        self.time_canvas = TimeCanvas(self)
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

        
        print("shutting down")
        event.accept()

    def tab_changed(self, index):
        # Get the index of the currently selected tab
        current_tab_index = self.tab_widget.currentIndex()
        print("Tab changed to:", current_tab_index)

class TimeCanvas(QWidget):
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

        # dsp variables
        self.file_name = "output.wav" # sample name
        self.fund_freq = int(220) # arbitrary
        # boot pyo server receiving all MIDI input devices
        self.pyo_server = Server()
        self.pyo_server.setMidiInputDevice(99)  # Open all MIDI input devices.
        self.pyo_server.boot()
        self.notes = Notein(poly=16, scale=1, first=0, last=127, channel=0, mul=1) # Receive midi from every channel
        self.sc = 0 #initialize scope value

        # Play sound button
        move_x = parent.screen_width
        self.chooseSoundButton = QPushButton('Choose Sound', self)
        self.chooseSoundButton.clicked.connect(self.chooseSound)
        self.chooseSoundButton.setGeometry(move_x-260, 0, 100, 30)
        #chooseSoundButton.setStyleSheet("background-color: lime;")

        self.clearButton = QPushButton('Clear', self)
        self.clearButton.clicked.connect(self.clearCanvas)
        self.clearButton.setGeometry(move_x-130, 0, 100, 30)
        self.clearButton.setStyleSheet("background-color: red;")

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

        if self.pyo_server.getIsStarted():
            self.pyo_server.stop()
            self.chooseSoundButton.setEnabled(True)

    def add_point(self, pos):
        self.x_values.append(pos.x() - self.width() / 2)
        self.y_values.append(pos.y() - self.height() / 2)

    def chooseSound(self):
        if (self.y_values == []):
            return
        y = np.array(self.y_values)
        max_norm = np.max(np.abs(y))
        wave = y / max_norm
        waveform = y / max_norm
        N = len(wave)
        duration = 5 # seconds
        sampling_freq = N*self.fund_freq 
        amplitude = 1

        for i in range(duration):
            for j in range(self.fund_freq):
                waveform = np.concatenate((waveform, wave))
        waveform = -1 * amplitude * waveform
        # Smooth out the signal
        w = 10 # Points to avg in the smoothing process
        waveform = convolve(waveform, Box1DKernel(w)) # boxcar smoothing
        # write waveform to a wav file
        signal_int16 = np.int16(waveform * 32767)
        write(self.file_name, sampling_freq, signal_int16)

        self.start_synth()

    def start_synth(self):
        file_path = os.getcwd() + "/" + self.file_name
        if (os.path.exists(file_path) == False):
            self.message_box(file_path + " DNE")
            return
        self.chooseSoundButton.setEnabled(False)
        self.pyo_server.start()
        vol = Midictl(ctlnumber=0, minscale=0, maxscale=1, init=0.2)
        atk = Midictl(ctlnumber=1, minscale=0, maxscale=10, init=0.005)
        rel = Midictl(ctlnumber=2, minscale=0, maxscale=10, init=0.8)

        trem_freq = (Midictl(ctlnumber=3, minscale=0, maxscale=35, init=4))
        lp_cutoff = (Midictl(ctlnumber=4, minscale=1, maxscale=10000, init=10000))

        tremolo = Sine(trem_freq)
        env = MidiAdsr(self.notes["velocity"], attack=0.05, decay=0.1, sustain=0.7, release=0.8, mul=vol)
        transpo = Sig(Bendin(brange=12, scale=1)) # Handle pitch bend

        src = SfPlayer(file_path, speed=self.notes["pitch"]*transpo/self.fund_freq, loop=True, offset=0, interp=2, mul=env, add=0).mix()*tremolo
        lp0 = MoogLP(src.mix(), lp_cutoff).out(0)
        lp1 = MoogLP(src.mix(), lp_cutoff).out(1)

        def set_vals():
            env.setRelease(rel.get())
            env.setAttack(atk.get())
        pat = Pattern(set_vals, time=0.1).play()

        sc = Scope(lp0)
        sc.view(title="Scope", wxnoserver=True)
        #self.notes.keyboard(wxnoserver=True)
         #.view(title="Scope", wxnoserver=True)

    def show_scope(self):
        self.sc.view(title="Scope", wxnoserver=True)

    def message_box(self, message):
        msg_box = QMessageBox()
        msg_box.setText(message)
        msg_box.exec_()

def main():
    app = QApplication(sys.argv)
    ex = Draw2SoundGUI()
    ex.show()
    #ex.showFullScreen()
    ex.showMaximized()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
