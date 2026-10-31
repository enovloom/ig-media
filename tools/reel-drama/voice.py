# Makes narration with a synthetic voice profile (voices/profiles.json) instead of a recording.
#   python3 voice.py <lines.json> <profile> <out dir>
# lines.json: { "lines": [...], "marks": { "name": { "line": 5, "prefix": "任せるときは、" } } }
# Writes out/lineNN.wav (speech only, silence trimmed, 48 kHz mono) and out/meta.json with each line's
# length, where each mark's words start inside its line, and the gain that brought the voice to -16 LUFS.
# Needs: apt-get install open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001
import json, os, subprocess, sys, tempfile, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DIC = '/var/lib/mecab/dic/open-jtalk/naist-jdic'
spec = json.load(open(sys.argv[1], encoding='utf-8'))
pid, out = sys.argv[2], sys.argv[3]
prof = json.load(open(os.path.join(HERE, 'voices', 'profiles.json'), encoding='utf-8'))[pid]
voice = prof['voice'] if os.path.isabs(prof['voice']) else os.path.join(HERE, prof['voice'])
os.makedirs(out, exist_ok=True)

def say(text):
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, 'in.txt'), 'w', encoding='utf-8') as f:
            f.write(text)
        subprocess.run(['open_jtalk', '-x', DIC, '-m', voice, '-r', str(prof['r']), '-fm', str(prof['fm']), '-jf', str(prof['jf']),
                        '-ow', os.path.join(d, 'o.wav'), os.path.join(d, 'in.txt')], check=True, capture_output=True)
        with wave.open(os.path.join(d, 'o.wav')) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768.0
            sr = w.getframerate()
    idx = np.where(np.abs(x) > np.abs(x).max() * 0.03)[0]
    # keep 20 ms on each side so no consonant is clipped
    pad = int(0.02 * sr)
    return x[max(0, idx[0] - pad):idx[-1] + pad], sr

def lufs(x, sr):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'a.wav')
        write(p, x, sr)
        log = subprocess.run(['ffmpeg', '-v', 'info', '-i', p, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    return float([l for l in log.splitlines() if l.strip().startswith('I:')][-1].split()[1])

def write(p, x, sr):
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())

lines = [say(t) for t in spec['lines']]
sr = lines[0][1]
# one gain for the whole voice, so the lines keep their balance and every profile plays at the same loudness
gain = 10 ** ((-16.0 - lufs(np.concatenate([x for x, _ in lines]), sr)) / 20)
gain = min(gain, 0.89 / max(np.abs(x).max() for x, _ in lines))
for i, (x, _) in enumerate(lines):
    write(os.path.join(out, f'line{i + 1:02d}.wav'), x * gain, sr)
marks = {k: round(len(say(m['prefix'])[0]) / sr - 0.02, 2) for k, m in spec.get('marks', {}).items()}
meta = {'profile': pid, **prof, 'lengths': [round(len(x) / sr, 3) for x, _ in lines], 'marks': marks, 'gain_db': round(20 * np.log10(gain), 1)}
with open(os.path.join(out, 'meta.json'), 'w', encoding='utf-8') as f:
    f.write(json.dumps(meta, ensure_ascii=False, indent=1) + '\n')
print(pid, prof['name'], 'lengths', meta['lengths'], 'marks', marks, 'gain', meta['gain_db'], 'dB')
