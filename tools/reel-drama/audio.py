# Synthesizes the reel soundtrack: a quiet lo-fi beat and pad, plus a sound for every chat event.
# An explainer can carry narration: "voice": [{ "t": 0.3, "file": "voice/line01.wav" }] (mono WAV, path relative to the
# JSON). The music drops while a line is spoken, and the voice-to-music level difference is printed.
# For a drama episode (style "drama") it is the music bed named by "bgm" (pad, comedy or none), the end chime,
# and the sound effect each subtitle names with "sfx" (see SFX below), played under the clips' own sound.
#   python3 audio.py scene.json out.wav
import json, sys, wave
import numpy as np

SR = 48000
scene = json.load(open(sys.argv[1], encoding='utf-8'))
drama = scene.get('style') == 'drama'
explainer = scene.get('style') == 'explainer'
if explainer:
    # an explainer names its sounds directly: "sfx": [{ "t": 1.2, "name": "pop" }]
    dur = scene['duration']
    events = [{'t': x['t'], 'type': 'sfx', 'name': x['name']} for x in scene.get('sfx', [])]
elif drama:
    clip_end = sum(c['dur'] for c in scene['clips'])
    dur = clip_end + scene['endDur']
    events = [{'t': clip_end, 'type': 'end'}] + [{'t': x['t'], 'type': 'sfx', 'name': x['sfx']} for x in scene['subs'] if x.get('sfx')]
else:
    dur = scene['duration']
    events = scene['events']
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
bgm = scene.get('bgm', 'pad') if drama else scene.get('bgm', 'chat')
b = 0
while bgm == 'chat' and b * beat < dur:
    t = b * beat
    add(kick if b % 2 == 0 else snare, t, 0.30 if b % 2 == 0 else 0.07)
    add(hat, t + beat / 2, 0.025)
    b += 1

# comedy: 116 BPM, short plucked chords C - Am - F - G on the off-beats over a light kick and hats
if bgm == 'comedy':
    cb = 60 / 116
    prog = [[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]]
    k = 0
    while k * cb < dur:
        t = k * cb
        add(kick, t, 0.22 if k % 2 == 0 else 0.0)
        add(hat, t + cb / 2, 0.02)
        for m in prog[(k // 4) % 4]:
            add(note(m + 12, 0.25, 0.06), t + cb / 2, 0.05)
        add(note(prog[(k // 4) % 4][0] - 12, 0.4, 0.12), t, 0.10)
        k += 1

# pad: Am - F - C - G, two bars each, slow attack
chords = [[57, 60, 64], [53, 57, 60], [48, 55, 60], [55, 59, 62]]
bar = beat * 4
c = 0
while bgm in ('chat', 'pad') and c * 2 * bar < dur:
    length = 2 * bar
    n = int(length * SR)
    t = np.arange(n) / SR
    shape = np.minimum(1, t / 0.6) * np.minimum(1, (length - t) / 0.6)
    pad = sum(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * t) for m in chords[c % 4]) * shape
    add(pad, c * 2 * bar, 0.05 if drama else 0.022)
    c += 1

# narration: each line placed at its time; the music bed is lowered under it (15 dB, short ramps)
import os
voice = np.zeros_like(mix)
spans = []
for v in scene.get('voice', []):
    with wave.open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), v['file'])) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1, 'narration must be mono 48 kHz WAV'
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768.0
    x = x / max(1e-6, np.max(np.abs(x))) * 0.9 * v.get('gain', 1)
    i = int(v['t'] * SR)
    n = min(len(x), len(voice) - i)
    voice[i:i + n] += x[:n]
    spans.append((v['t'], v['t'] + len(x) / SR))
if spans:
    duck = np.ones_like(mix)
    ramp = int(0.15 * SR)
    for a, b in spans:
        i, j = int(a * SR), int(b * SR)
        duck[max(0, i - ramp):j + ramp] = 10 ** (-15 / 20)
    duck = np.convolve(duck, np.ones(ramp) / ramp, mode='same')
    mix *= duck
    rms = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
    under = np.concatenate([mix[int(a * SR):int(b * SR)] for a, b in spans])
    spoken = np.concatenate([voice[int(a * SR):int(b * SR)] for a, b in spans])
    print(f'voice {rms(spoken):.1f} dB, music under it {rms(under):.1f} dB, difference {rms(spoken) - rms(under):.1f} dB', file=sys.stderr)
    mix += voice

pop_l = tone(620, 480, 0.09, 0.03)
pop_r = tone(880, 1180, 0.09, 0.03)

def layer(*sigs):
    # sums sounds of different lengths
    out = np.zeros(max(len(x) for x in sigs))
    for x in sigs:
        out[:len(x)] += x
    return out

def chord(midis, length, decay, spread=0.0):
    out = np.zeros(int((length + spread * len(midis)) * SR))
    for i, m in enumerate(midis):
        w = note(m, length, decay)
        j = int(i * spread * SR)
        out[j:j + len(w)] += w
    return out

def sweep(length):
    # a whoosh: noise that swells and fades, brighter in the middle
    n = int(length * SR)
    t = np.linspace(0, 1, n)
    w = np.random.default_rng(3).standard_normal(n)
    w = np.convolve(w, np.ones(6) / 6, mode='same') * 0.6 + w * 0.4 * np.sin(np.pi * t)
    return w * np.sin(np.pi * t) ** 2

# sound effects a subtitle can name with "sfx", each with its gain in the mix
SFX = {
    'pop': (pop_r, 0.26),                                                    # a line appears
    'tsukkomi': (layer(noise(0.08, 0.02), 0.8 * tone(220, 110, 0.12, 0.04)), 0.5), # paper-fan slap for a sharp 本音
    'don': (layer(tone(95, 35, 0.7, 0.25), 0.5 * noise(0.3, 0.06, smooth=8)), 0.6), # heavy impact
    'gaan': (layer(chord([48, 51, 54, 57], 1.4, 0.6), chord([36, 39, 42], 1.4, 0.6)), 0.16), # shock chord
    'kira': (chord([96, 100, 103, 108], 0.5, 0.15, spread=0.05), 0.08),      # sparkle
    'whoosh': (sweep(0.45), 0.18),                                           # scene change
    'ding': (np.concatenate([note(88, 0.18, 0.12), note(84, 0.5, 0.25)]), 0.14), # correct
    'buzz': (sum(np.sin(2 * np.pi * 140 * h * np.arange(int(0.5 * SR)) / SR) / h for h in (1, 3, 5)) * env(int(0.5 * SR), decay=0.4), 0.12), # wrong
}
for ev in events:
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
    elif k == 'sfx':
        sig, gain = SFX[ev['name']]
        add(sig, t, gain)
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
