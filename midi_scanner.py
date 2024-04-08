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
scan2 = Notein()
notes = Notein(poly=16, scale=1, first=0, last=127, channel=0, mul=1)


# These functions are called when Notein receives a MIDI note event.
def noteon(voice):
    "Print pitch and velocity for noteon event."
    pit = int(notes["pitch"].get(all=True)[voice])
    vel = int(notes["velocity"].get(all=True)[voice] * 127)
    print("Noteon: voice = %d, pitch = %d, velocity = %d" % (voice, pit, vel))


def noteoff(voice):
    "Print pitch and velocity for noteoff event."
    pit = int(notes["pitch"].get(all=True)[voice])
    vel = int(notes["velocity"].get(all=True)[voice] * 127)
    print("Noteoff: voice = %d, pitch = %d, velocity = %d" % (voice, pit, vel))


# TrigFunc calls a function when it receives a trigger. Because notes["trigon"]
# contains 10 streams, there will be 10 caller, each one with its own argument,
# taken from the list of integers given at `arg` argument.
tfon = TrigFunc(notes["trigon"], noteon, arg=list(range(10)))
tfoff = TrigFunc(notes["trigoff"], noteoff, arg=list(range(10)))

s.gui(locals())