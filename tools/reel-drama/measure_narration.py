# Reads each narration line with Open JTalk at its normal speed and prints how long the speech itself lasts
# (silence at both ends trimmed), so cuts are timed to a real reading instead of a guess; also writes each
# line as a WAV. A person reads at their own pace, so re-time once the real voice is recorded.
#   python measure_narration.py '["次はこう伝える。", "..."]' <out dir>
# Needs a Python 3.11 venv: uv venv -p python3.11 tts && uv pip install -p tts/bin/python pyopenjtalk-prebuilt "numpy<2" "setuptools<81"
import sys, json, wave
import numpy as np
import pyopenjtalk

lines = json.loads(sys.argv[1])
out = sys.argv[2]
res = []
for i, text in enumerate(lines):
    x, sr = pyopenjtalk.tts(text)
    a = np.abs(x)
    th = a.max() * 0.03
    idx = np.where(a > th)[0]
    s, e = idx[0] / sr, idx[-1] / sr
    res.append({'text': text, 'speech': round(e - s, 2), 'total': round(len(x) / sr, 2)})
    pcm = np.clip(x[idx[0]:idx[-1]] / 32768.0, -1, 1)
    with wave.open(f'{out}/line{i + 1:02d}.wav', 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((pcm * 32767).astype(np.int16).tobytes())
print(json.dumps(res, ensure_ascii=False, indent=1))
