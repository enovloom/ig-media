# reel-drama

Chat-style short drama reels in the same look as the `reel_chat` posts (1080x1920, 30fps).
An episode is one JSON file in `episodes/`: the chat lines with their start times, an optional stamp, and the end card.

```sh
mkdir -p fonts && for w in 500:CMj75s 700:PYk75s 900:Lgk75s; do
  curl -sS -o fonts/NotoSansJP-${w%%:*}.ttf "https://fonts.gstatic.com/s/notosansjp/v57/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VF${w##*:}.ttf"; done
python3 audio.py episodes/<id>.json audio.wav
node render.js episodes/chat-ep1.json --stills 1,10,30   # check the layout
node render.js episodes/<id>.json audio.wav video.mp4
```

## Drama episodes

A drama episode (`"style": "drama"`, e.g. `episodes/drama-ep1.json`) is cut from generated video clips
(Google Flow / Veo, 9:16, about 8 seconds each). The JSON holds the fixed cast, one prompt per clip,
the subtitles and the end card; the finished reel gets the same label, hook title and end card as the chat reels.

```sh
node drama.js episodes/drama-ep1.json --prompts               # prompts to paste into Flow, cast filled in
node drama.js episodes/drama-ep1.json <clips dir> video.mp4   # clips named 01.mp4, 02.mp4, ... as in the JSON
```

Photos work as clips too (slow camera moves), and subtitles can carry 建前/本音 tags and sound effects;
`episodes/honne-sample.json` shows that format. `.claude/skills/make-reel/SKILL.md` has every field and the rules.

Check every reel before booking it; this also writes `video.sheet.png`, a frame every 2 seconds:

```sh
node check.js video.mp4 episodes/<id>.json
```

After a draft, make the review pack for ChatGPT (frames at 1, 3 and 5 s as JPEGs, and review.txt with the
script, each cut's start and end, the placeholder material and what is unchecked):

```sh
node review.js video.mp4 drafts/<id>/<id>.json drafts/<id>/review drafts/<id>/brief.md
```

Narration is a synthetic voice, never the account owner's recording. `voice.py` reads the lines with one of the
profiles in `voices/profiles.json` (A male calm, B male bright, C female calm, D female bright) and records each
line's length for timing; it needs `apt-get install open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001`.
The Mei voice files in `voices/mei/` are CC BY 3.0 (see COPYRIGHT.txt). `measure_narration.py` is the older
way of timing lines with pyopenjtalk.

Needs Node with Playwright (Chromium), ffmpeg, and Python 3 with numpy.
