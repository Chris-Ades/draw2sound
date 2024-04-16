from pyo import *
import os
# file_path: directory path of a sound
# fund freq: fundamental frequency of the sound
#notes: pyo object for midi input
class D2S_synth:
    def __init__(self, fund_freq, notes, file_path):
        # if file_path is not given then create a null wave file right here and use that
        #set path must be used to update the sample

        self.notes = notes
            
        self.vol = Log10(Midictl(ctlnumber=0, minscale=10**0.01, maxscale=10**1, init=10**0.2))
        self.atk = (Midictl(ctlnumber=1, minscale=0, maxscale=10, init=0.005))
        self.rel = (Midictl(ctlnumber=2, minscale=0, maxscale=10, init=0.8))

        self.trem_freq = (Midictl(ctlnumber=3, minscale=0, maxscale=20, init=0.1))
        self.lp_cutoff = (Midictl(ctlnumber=4, minscale=0.1, maxscale=4000, init=4000))

        self.tremolo = Sine(self.trem_freq)
        self.env = MidiAdsr(notes["velocity"], attack=0.05, decay=0.1, sustain=0.7, release=0.8, mul=self.vol) 
        self.transpo = Sig(Bendin(brange=12, scale=1)) 

        self.src = SfPlayer(file_path, speed=self.notes["pitch"]*self.transpo/fund_freq, loop=True, offset=0, interp=2, mul=self.env, add=0)
        
        self.lp0 = MoogLP(self.src.mix(), self.lp_cutoff)
        #self.rev0 = STRev(self.lp0)
        self.comp0 = Compress(self.lp0.mix(), thresh=-15)

        self.src_trem = self.src * self.tremolo
        self.lp1 = MoogLP(self.src_trem.mix(), self.lp_cutoff)
        #self.rev1 = STRev(self.lp1)
        self.comp1 = Compress(self.lp1.mix(), thresh=-15)

        def set_vals():
            self.env.setRelease(self.rel.get())
            self.env.setAttack(self.atk.get())
        self.pat = Pattern(set_vals, time=0.05).play()

    def out(self):
        self.comp0.out(0)
        self.comp1.out(1)
    
    def setPath(self, path):
        self.src.setPath(path)

    def setFundFreq(self, fund_freq):
        self.src.setSpeed(self.notes["pitch"]*self.transpo/fund_freq)

    def stop(self):
        self.comp0.stop()
        self.comp1.stop()
        self.lp0.stop()
    
    def start(self):
        self.comp0.play()
        self.comp1.play()
        self.lp0.play()

    def sig(self):
        return (self.lp0).mix()



        