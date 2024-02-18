from pyo import *
import os

file_path = "/home/user/Desktop/Music/draw2sound/v1.0/output.wav"
if os.path.exists(file_path):
    print("The file exists.")
else:
    print("The file does not exist.")

s = Server().boot()

table = SndTable(file_path)
table.view()

looper = Looper(
    table=table,  # The table to read.
    pitch=1.0,  # Speed factor, 0.5 means an octave lower,
    # 2 means an octave higher.
    start=0,  # Start time of the loop, in seconds.
    dur=table.getDur(),  # Duration of the loop, in seconds.
    xfade=25,  # Duration of the crossfade, in % of the loop length.
    mode=1,  # Looping mode: 0 = no loop, 1 = forward,
    #               2 = backward, 3 = back-and-forth.
    xfadeshape=0,  # Shape of the crossfade envelope: 0 = linear
    #   1 = equal power, 2 = sigmoid.
    startfromloop=False,  # If True, the playback starts from the loop start
    # point. If False, the playback starts from the
    # beginning and enters the loop mode when crossing
    # the loop start point.
    interp=4,  # Interpolation method (used when speed != 1):
    # 1 = none, 2 = linear, 3 = cosine, 4 = cubic.
    autosmooth=True,  # If True, a lowpass filter, following the pitch,
    # is applied on the output signal to reduce the
    # quantization noise produced by very low transpositions.
    # interp = 4 and autosmooth = True give a very high
    # quality reader for playing sound at low rates.
    mul=0.5,
)
looper.ctrl()

stlooper = looper.mix(2).out()

s.gui(locals())