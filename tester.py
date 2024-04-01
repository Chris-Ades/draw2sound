from pyo import *
import time

file_path = os.getcwd() + "/output.wav"
if os.path.exists(file_path):
    print("The file exists.")
else:
    print("The file does not exist.")

s = Server()
s.setMidiInputDevice(99)  # Open all input devices.
s.boot().start()

# Automatically converts MIDI pitches to frequencies in Hz.
notes = Notein(scale=1)
notes.keyboard()

vol = Midictl(ctlnumber=88, minscale=0, maxscale=1, init=0.2)
#rel = Midictl(ctlnumber=3, minscale=0, maxscale=3, init=0.5)

env = MidiAdsr(notes["velocity"], attack=0.005, decay=0.1, sustain=0.7, release=0.6, mul=vol)

# Handle pitch bend
transpo = Sig(Bendin(brange=12, scale=1))

fund_freq = 440

# make speed = Notein / actual frequency
srcR = SfPlayer(file_path, speed=notes["pitch"]*transpo/fund_freq, loop=True, offset=0, interp=2, mul=env, add=0).out(0)
srcL = SfPlayer(file_path, speed=notes["pitch"]*transpo/fund_freq, loop=True, offset=0, interp=2, mul=env, add=0).out(1)

sc = Scope(srcR + srcL)
sp = Spectrum(srcR + srcL)


s.gui()
