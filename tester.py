import numpy as np
from scipy.signal import lfilter, butter
import pyaudio
import matplotlib.pyplot as plt

# Function to apply formant filtering
def apply_formant_filter(input_signal, formant_freqs, samplerate, gain=1.0):
    output_signal = np.copy(input_signal)
    nyquist_freq = samplerate / 2.0
    for f in formant_freqs:
        # Normalize formant frequency
        normalized_freq = f / nyquist_freq
        # Design formant filter using second-order sections
        b, a = butter(2, [0.9*normalized_freq, 1.1*normalized_freq], btype='band')
        output_signal = lfilter(b, a, output_signal) * gain
    return output_signal

# Read input signal (replace this with your actual signal)
input_signal = np.random.randn(44100)  # Example random input signal
samplerate = 44100

# Define formant frequencies for 'oooh' sound
formant_freqs_oooh = [300, 870, 2250, 2450, 3500]

# Apply formant filtering
output_signal = apply_formant_filter(input_signal, formant_freqs_oooh, samplerate)

# Play processed signal
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paFloat32, channels=2, rate=samplerate, output=True)
stream.write(output_signal.astype(np.float32).tobytes())
stream.close()
p.terminate()


plt.plot(output_signal)
plt.title('Waveform')
plt.show()

# file_name = "output.wav"
# signal_int16 = np.int16(waveform * 32767)
# write(file_name, sampling_freq, signal_int16)
