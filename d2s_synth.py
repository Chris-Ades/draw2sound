from pyo import *
# file_path: directory path of a sound
# fund freq: fundamental frequency of the sound
#notes: pyo object for midi input
class Synth:
    def __init__(self, file_path, fund_freq, notes):

        self.vol = Midictl(ctlnumber=0, minscale=0, maxscale=1, init=0.2)
        self.atk = Midictl(ctlnumber=1, minscale=0, maxscale=10, init=0.005)
        self.rel = Midictl(ctlnumber=2, minscale=0, maxscale=10, init=0.8)

        self.trem_freq = (Midictl(ctlnumber=3, minscale=0, maxscale=35, init=4))
        self.lp_cutoff = (Midictl(ctlnumber=4, minscale=1, maxscale=10000, init=10000))

        self.tremolo = Sine(self.trem_freq)
        self.env = MidiAdsr(notes["velocity"], attack=0.05, decay=0.1, sustain=0.7, release=0.8, mul=self.vol) # Controls self.envelope
        self.transpo = Sig(Bendin(brange=12, scale=1)) # Handle pitch bend

        self.src = SfPlayer(file_path, speed=notes["pitch"]*self.transpo/fund_freq, loop=True, offset=0, interp=2, mul=self.env, add=0).mix()*self.tremolo
        self.lp0 = MoogLP(self.src.mix(), self.lp_cutoff)
        self.lp1 = MoogLP(self.src.mix(), self.lp_cutoff)

        def set_vals():
            self.env.setRelease(self.rel.get())
            self.env.setAttack(self.atk.get())
        self.pat = Pattern(set_vals, time=0.1).play()

    def out(self):
        self.lp0.out(0)
        self.lp1.out(1)
    
    def stop(self):
        self.lp0.stop()
        self.lp1.stop()

    def sig(self):
        return self.lp0



        