# Writes each profile's narration alone (no music), placed exactly as in its preview. All four get the same
# loudness: the loudest one every file reaches with a plain gain change and peaks at or under -1.5 dBFS
# (no compression or limiting, so no version is processed differently from another).
#   python3 voice_only.py
import json, os, subprocess, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {'A': 'A_male_calm', 'B': 'B_male_bright', 'C': 'C_female_calm', 'D': 'D_female_bright'}
def lufs(p):
    log = subprocess.run(['ffmpeg', '-v', 'info', '-i', p, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = float([l for l in log.splitlines() if l.strip().startswith('I:')][-1].split()[1])
    P = float([l for l in log.splitlines() if l.strip().startswith('Peak:')][-1].split()[1])
    return I, P
tracks = {}
for pid, name in NAMES.items():
    ep = json.load(open(os.path.join(HERE, f'preview-{pid}.json'), encoding='utf-8'))
    sr = 48000
    x = np.zeros(int(ep['duration'] * sr) + 1)
    for v in ep['voice']:
        with wave.open(os.path.join(HERE, v['file'])) as w:
            y = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768.0
        i = int(v['t'] * sr); x[i:i + len(y)] += y[:len(x) - i]
    tracks[pid] = (name, x, ep['duration'])
def write(p, x):
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
reach = {}
for pid, (name, x, _) in tracks.items():
    p = os.path.join(HERE, f'{name}.wav'); write(p, x); I, P = lufs(p)
    reach[pid] = (I, P, I + (-1.5 - P))
target = np.floor(min(r[2] for r in reach.values()) * 10) / 10
for pid, (name, x, dur) in tracks.items():
    I, P, _ = reach[pid]
    out = os.path.join(HERE, f'{name}.wav')
    write(out, x * 10 ** ((target - I) / 20))
    I2, P2 = lufs(out)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', out, '-c:a', 'aac', '-b:a', '192k', out.replace('.wav', '.m4a')], check=True)
    print(f'{name}: {dur:.2f}s, {I2:.1f} LUFS, peak {P2:.1f} dBFS')
print('common loudness', target, 'LUFS')
