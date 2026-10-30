# reel-drama

Chat-style short drama reels in the same look as the `reel_chat` posts (1080x1920, 30fps).
An episode is one JSON file in `episodes/`: the chat lines with their start times, an optional stamp, and the end card.

```sh
mkdir -p fonts && for w in 500:CMj75s 700:PYk75s 900:Lgk75s; do
  curl -sS -o fonts/NotoSansJP-${w%%:*}.ttf "https://fonts.gstatic.com/s/notosansjp/v57/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VF${w##*:}.ttf"; done
python3 audio.py episodes/<id>.json audio.wav
node render.js episodes/<id>.json --stills 1,10,30   # check the layout
node render.js episodes/<id>.json audio.wav video.mp4
```

Needs Node with Playwright (Chromium), ffmpeg, and Python 3 with numpy.
