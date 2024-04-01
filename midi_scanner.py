from pyo import *

# Print the list of available MIDI devices to the console.
pm_list_devices()

s = Server(duplex=0)

# Give the ID of the desired device (as listed by pm_list_devices()) to the
# setMidiInputDevice() of the Server. A bigger number than the higher device
# ID will open all connected MIDI devices.
s.setMidiInputDevice(99)

# The MIDI device must be set before booting the server.
s.boot().start()

print("Play with your Midi controllers...")

# Function called by CtlScan2 object.
def scanner(ctlnum, midichnl):
    print("MIDI channel: %d, controller number: %d" % (midichnl, ctlnum))


# Listen to controller input.
scan = CtlScan2(scanner, toprint=False)

s.gui(locals())