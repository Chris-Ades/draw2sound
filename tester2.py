from pyo import *

s = Server()
s.setMidiInputDevice(99) # opens all devices
s.boot()
s.start()
def event(status, data1, data2):
    print(status, data1, data2)
a = RawMidi(event)

s.gui()