from pyo import *

fund_freq = 440

file_path = os.getcwd() + "/output.wav"
if os.path.exists(file_path):
    print("The file exists.")
else:
    print("The file does not exist.")

s = Server()
s.setMidiInputDevice(99)  # Open all input devices.
s.boot().start()

# Automatically converts MIDI pitches to frequencies in Hz.
notes = Notein(poly=16, scale=1, first=0, last=127, channel=0, mul=1)
notes.keyboard()

vol = Midictl(ctlnumber=0, minscale=0, maxscale=1, init=0.2)
atk = Midictl(ctlnumber=1, minscale=0, maxscale=10, init=0.005)
rel = Midictl(ctlnumber=2, minscale=0, maxscale=10, init=0.8)

trem_freq = (Midictl(ctlnumber=3, minscale=0, maxscale=35, init=1))
lp_cutoff = (Midictl(ctlnumber=4, minscale=1, maxscale=10000, init=10000))
#hp_cutoff = (Midictl(ctlnumber=86, minscale=1, maxscale=10000, init=1))

tremolo = Sine(trem_freq)
env = MidiAdsr(notes["velocity"], attack=0.05, decay=0.1, sustain=0.7, release=0.8, mul=vol) # Controls envelope
transpo = Sig(Bendin(brange=12, scale=1)) # Handle pitch bend

src = SfPlayer(file_path, speed=notes["pitch"]*transpo/fund_freq, loop=True, offset=0, interp=2, mul=env, add=0).mix()*tremolo
#hp = ButHP(src, hp_cutoff)
lp0 = MoogLP(src.mix(), lp_cutoff).out(0)
lp1 = MoogLP(src.mix(), lp_cutoff).out(1)

# ADD A COMPRESSOR SO VOLUME DOESN'T GO ABOVE CERTAIN LEVEL

sc = Scope(lp0)
# show all notes unmixed
sp = Spectrum(lp0)
sp.setSize(4096)
sp.setFscaling(True)

# Update attack and release values
def set_vals():
    env.setRelease(rel.get())
    env.setAttack(atk.get())
    #tremolo
    #hipass cutoff
    #lopass cutoff
pat = Pattern(set_vals, time=0.1).play()


s.gui()