# Synthesizes the reel soundtrack: a quiet lo-fi beat and pad, plus a sound for every chat event.
#   python3 audio.py scene.json out.wav
import json, sys, wave
import numpy as np

SR = 48000
scene = json.load(open(sys.argv[1], encoding='utf-8'))
dur = scene['duration']
mix = np.zeros(int(SR * dur) + SR)

def add(sig, t, gain=1.0):
    i = int(t * SR)
    n = min(len(sig), len(mix) - i)
    if n > 0:
        mix[i:i + n] += sig[:n] * gain

def env(n, attack=0.005, decay=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t / decay)

def tone(freq_from, freq_to, length, decay, shape='sine'):
    n = int(length * SR)
    f = np.linspace(freq_from, freq_to, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = np.sin(ph) if shape == 'sine' else (2 / np.pi) * np.arcsin(np.sin(ph))
    return w * env(n, decay=decay)

def noise(length, decay, smooth=1):
    n = int(length * SR)
    w = np.random.default_rng(7).standard_normal(n)
    if smooth > 1:
        w = np.convolve(w, np.ones(smooth) / smooth, mode='same')
    return w * env(n, attack=0.001, decay=decay)

def note(midi, length, decay, gain=1.0):
    f = 440 * 2 ** ((midi - 69) / 12)
    n = int(length * SR)
    t = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
    return w * env(n, attack=0.004, decay=decay) * gain

# beat: 92 BPM, kick on 1 and 3, soft snare on 2 and 4, hats on eighths
beat = 60 / 92
kick = tone(130, 45, 0.35, 0.12)
snare = noise(0.2, 0.05, smooth=3)
hat = noise(0.05, 0.012)
b = 0
while b * beat < dur:
    t = b * beat
    add(kick if b % 2 == 0 else snare, t, 0.30 if b % 2 == 0 else 0.07)
    add(hat, t + beat / 2, 0.025)
    b += 1

# pad: Am - F - C - G, two bars each, slow attack
chords = [[57, 60, 64], [53, 57, 60], [48, 55, 60], [55, 59, 62]]
bar = beat * 4
c = 0
while c * 2 * bar < dur:
    length = 2 * bar
    n = int(length * SR)
    t = np.arange(n) / SR
    shape = np.minimum(1, t / 0.6) * np.minimum(1, (length - t) / 0.6)
    pad = sum(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * t) for m in chords[c % 4]) * shape
    add(pad, c * 2 * bar, 0.022)
    c += 1

pop_l = tone(620, 480, 0.09, 0.03)
pop_r = tone(880, 1180, 0.09, 0.03)
for ev in scene['events']:
    t, k = ev['t'], ev['type']
    if k == 'left':
        add(pop_l, t, 0.30)
    elif k == 'right':
        add(pop_r, t, 0.26)
    elif k == 'pill':
        add(tone(392, 370, 0.4, 0.18, 'tri'), t, 0.12)
    elif k == 'date':
        add(note(76, 0.6, 0.25), t, 0.12)
        add(note(81, 0.8, 0.35), t + 0.14, 0.12)
    elif k == 'stamp':
        add(tone(160, 50, 0.4, 0.14), t, 0.45)
        for i, m in enumerate([84, 88, 91]):
            add(note(m, 0.8, 0.3), t + 0.02 + i * 0.03, 0.09)
    elif k == 'end':
        for i, m in enumerate([72, 76, 79, 84]):
            add(note(m, 0.9, 0.35), t + i * 0.09, 0.13)

mix = mix[:int(SR * dur)]
fade = int(0.8 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)
mix *= 10 ** (-7 / 20) / np.max(np.abs(mix))
pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open(sys.argv[2], 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(np.repeat(pcm, 2).tobytes())
