# Lays out the explainer JSON from the narration: each line's measured length decides when it starts and what
# appears on screen with it. The narration is a synthetic voice (voice.py), never the owner's own voice.
#   python3 build.py [voice dir] [out json]     defaults: voice  first-reel.json
# A voice dir made by voice.py carries meta.json: the profile's pace (pauses between lines) and where the words
# that bring in a picture start inside their line.
import json, os, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = sys.argv[1] if len(sys.argv) > 1 else 'voice'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'first-reel.json'
LINES = json.load(open(os.path.join(HERE, 'lines.json'), encoding='utf-8'))['lines']
meta_file = os.path.join(HERE, VOICE, 'meta.json')
meta = json.load(open(meta_file, encoding='utf-8')) if os.path.exists(meta_file) else {}
PACE = meta.get('pace', 1.0)
# 「判断できる範囲」 and 「一緒に渡す」 start this far into the last line
AT_HANDAN = meta.get('marks', {}).get('handan', 0.98)
AT_ISSHO = meta.get('marks', {}).get('issho', 2.75)

def length(i):
    with wave.open(os.path.join(HERE, VOICE, f'line{i + 1:02d}.wav')) as w:
        return w.getnframes() / w.getframerate()

d = [length(i) for i in range(len(LINES))]
BREATH, READ = 0.4 * PACE, max(0.85, 1.0 * PACE)
v = [0.3]                                   # cut 1: the problem is on screen from the first frame
e1 = v[0] + d[0]
cut2 = e1 + 0.5 * PACE
# cut 1's text fades once its line is said; cut 2's comes in after it is gone, and before its own line starts
fade1 = max(e1, cut2 - 0.45)
show2 = max(fade1 + 0.25, cut2 - 0.2)
v.append(max(cut2 + 0.1, show2 + 0.3))
e2 = v[1] + d[1]
cut3 = e2 + 0.6 * PACE                      # a moment to think about one's own way of handing over
v.append(cut3 + 0.1)
v.append(v[2] + d[2] + BREATH)
v.append(v[3] + d[3] + 0.5 * PACE)
cut4 = v[4] + d[4] + READ                   # time to read the two zones
v.append(cut4 + 0.1)
end = v[5] + d[5] + 1.3 * PACE
r = lambda x: round(x, 2)

items = [
    # cut 1, all visible at the first frame: the handed-over task, the one question, and who asks whom
    # each cut's text is gone before the next cut's comes in, so two lines never overlap
    {'type': 'text', 't0': -0.3, 't1': r(fade1), 'x': 80, 'y': 330, 'size': 88, 'text': '任せたのに、[[毎回]]'},
    {'type': 'avatar', 't0': -0.3, 't1': r(cut3), 'x': 250, 'y': 900, 'icon': '🧑‍💼', 'name': '店長', 'fadeTo': {'t': r(fade1), 'opacity': 0.18}},
    {'type': 'avatar', 't0': -0.3, 't1': r(cut3), 'x': 830, 'y': 900, 'icon': '🧑', 'name': 'スタッフ', 'fadeTo': {'t': r(fade1), 'opacity': 0.18}},
    {'type': 'card', 't0': -0.3, 't1': r(cut3), 'from': [610, 900], 'to': [610, 900], 'move': [0, 0.01], 'icon': '📋', 'text': '仕事', 'fadeTo': {'t': r(fade1), 'opacity': 0.18}},
    {'type': 'bubble', 't0': -0.3, 't1': r(fade1), 'x': 740, 'y': 640, 'text': 'どうしますか？'},
    # cut 2
    # cut 2: above the dimmed people, not on top of them
    {'type': 'text', 't0': r(show2), 't1': r(max(e2, cut3 - 0.25)), 'x': 60, 'y': 500, 'w': 960, 'size': 86, 'align': 'center', 'text': '[[「あとは任せる」]]で、\n終わってない？'},
    # cut 3 (adopted 2026-10-31: the supply example, fictional)
    {'type': 'text', 't0': r(cut3), 't1': r(cut4 - 0.3), 'x': 80, 'y': 330, 'size': 76, 'text': '次はこう伝える。'},
    {'type': 'zone', 'style': 'solid', 't0': r(v[3] - 0.1), 'x': 100, 'y': 560, 'w': 830, 'h': 270, 'tag': '✓ 自分で決めてよい', 'quote': 'いつもの備品を補充', 'quoteT': r(v[3]), 'moveTo': {'t': r(cut4), 'dur': 0.7, 'dy': 0, 'scale': 0.72}},
    {'type': 'zone', 'style': 'dashed', 't0': r(v[4] - 0.1), 'x': 100, 'y': 880, 'w': 830, 'h': 270, 'tag': '💬 相談して決める', 'quote': '別の商品へ変更', 'quoteT': r(v[4]), 'moveTo': {'t': r(cut4), 'dur': 0.7, 'dy': -90, 'scale': 0.72}},
    # cut 4: the formula comes in on 「判断できる範囲」, the last words on 「一緒に渡す」
    {'type': 'text', 't0': r(cut4), 'x': 80, 'y': 330, 'size': 76, 'text': '任せるときは、'},
    {'type': 'formula', 't0': r(v[5] + AT_HANDAN - 0.05), 'x': 60, 'y': 1110, 'w': 960, 'size': 62, 'text': '{{仕事}} ＋ [[判断できる範囲]]'},
    {'type': 'text', 't0': r(v[5] + AT_ISSHO - 0.05), 'x': 60, 'y': 1240, 'w': 960, 'size': 68, 'align': 'center', 'text': 'を、一緒に渡す'},
]
cuts = [
    {'t0': 0.0, 't1': r(cut2), 'narration': LINES[0], 'role': '任せたのに確認が戻る悩みを、最初の一画面で分からせる', 'material': '図のみ（店長とスタッフ、渡した仕事のカード、質問の吹き出し1つ）'},
    {'t0': r(cut2), 't1': r(cut3), 'narration': LINES[1], 'role': '自分の伝え方を振り返る間', 'material': '図のみ（人物とカードを薄くし、一文を見せる）'},
    {'t0': r(cut3), 't1': r(cut4), 'narration': LINES[2] + '「' + LINES[3].rstrip('。') + '。' + LINES[4].rstrip('。') + '」', 'role': 'あいまいな指示を、具体的な仕事で判断の範囲として示す', 'material': '図のみ（2つの領域。説明用の架空例「備品の補充」）'},
    {'t0': r(cut4), 't1': r(end), 'narration': LINES[5], 'role': '次に任せるときの行動を思い出せるようにする', 'material': '図のみ（縮めた2つの領域と式）'},
]
ep = {
    'style': 'explainer', 'template': 'explainer.html', 'fps': 30, 'duration': r(end), 'label': '店長の任せ方', 'bgm': 'chat',
    'note': 'reel-director の同梱例 first-reel.txt（架空の説明例）を図だけで組んだ試作。カット3の「備品の補充」も架空例で、本人の実話や実際の職場ルールではない。'
            + f"ナレーションは合成音声（Open JTalk{'、' + meta['profile'] + ' ' + meta['name'] if meta else ''}）で、本人の声ではない",
    'voiceProfile': meta.get('profile'),
    # narration paths are relative to the JSON, wherever it is written
    'voice': [{'t': r(t), 'file': os.path.relpath(os.path.join(HERE, VOICE, f'line{i + 1:02d}.wav'), os.path.dirname(os.path.join(HERE, OUT))), 'text': LINES[i]} for i, t in enumerate(v)],
    'sfx': [],
    'cuts': cuts,
    'items': items,
}
with open(os.path.join(HERE, OUT), 'w', encoding='utf-8') as f:
    f.write(json.dumps(ep, ensure_ascii=False, indent=2) + '\n')
for x in ep['voice']:
    print(f"{x['t']:5.2f}  {x['text']}")
print('cuts', [(c['t0'], c['t1']) for c in cuts], 'duration', ep['duration'])

# script.txt: the narration, the cuts, where each narration line sits, and when each piece of text appears
def plain(it):
    if it['type'] in ('text', 'formula'):
        return it['text'].replace('[[', '').replace(']]', '').replace('{{', '').replace('}}', '').replace('\n', '／')
    return {'bubble': lambda: f"吹き出し「{it['text']}」（スタッフから）", 'zone': lambda: f"{it['tag']} ／ {it['quote']}",
            'avatar': lambda: f"人物「{it['name']}」", 'card': lambda: '「仕事」のカード（スタッフの横、渡したあと）'}[it['type']]()
out = ['任せるときは、判断できる範囲も渡す（試作の台本）',
       '扱い: reel-director 同梱例 first-reel.txt の架空の説明例。本人の実体験ではない。',
       'カット3の「備品の補充」も説明用の架空例で、実際の職場のルールではない。',
       f"ナレーションは合成音声（Open JTalk{'、' + meta['profile'] + ' ' + meta['name'] if meta else ''}）。本人の声ではなく、本人に似せてもいない。", '',
       '【ナレーション】', *LINES, '',
       f"【カット（全体 {ep['duration']}秒）】",
       *[f"カット{i}  {c['t0']:.2f}〜{c['t1']:.2f}秒　{c['narration']}" for i, c in enumerate(cuts, 1)], '',
       '【ナレーションの位置（秒）】',
       *[f"{t:5.2f}〜{t + d[i]:5.2f}  {LINES[i]}" for i, t in enumerate(v)], '',
       '【画面の文字（出る時刻〜消え始める時刻）】']
for it in sorted(items, key=lambda i: i.get('quoteT', i['t0'])):
    t1 = it.get('t1')
    out.append(f"{max(0, it.get('quoteT', it['t0'])):5.2f}〜{(f'{t1:5.2f}' if t1 is not None else '最後'):>5}  {plain(it)}")
with open(os.path.join(HERE, 'script.txt' if OUT == 'first-reel.json' else OUT.replace('.json', '.script.txt')), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out) + '\n')
