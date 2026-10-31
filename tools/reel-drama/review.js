// Makes the review pack for ChatGPT from a finished draft:
// frames at 1, 3 and 5 seconds as separate full-size JPEGs, and review.txt with the whole script,
// every cut's start and end, the placeholder material and what has not been checked.
//   node review.js <video.mp4> <episode.json> <out dir> [brief.md]
const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const [video, epFile, outDir, briefFile] = process.argv.slice(2);
const ep = JSON.parse(fs.readFileSync(epFile, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });
const f1 = (x) => Number(x).toFixed(1);
const one = (s) => String(s).replace(/\n/g, '／');
const L = [];

const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration,size:stream=codec_type,width,height', '-of', 'json', video]).toString());
const dur = Number(probe.format.duration);
const vs = probe.streams.find((s) => s.codec_type === 'video');

// 1. frames, full size so the subtitles stay readable; seeking after -i makes the frame exact
const frames = [];
for (const t of [1, 3, 5]) {
  if (t >= dur) continue;
  const name = `frame_${String(t).padStart(2, '0')}s.jpg`;
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', video, '-ss', String(t), '-frames:v', '1', '-q:v', '2', path.join(outDir, name)]);
  frames.push(`${name}（${t}.0秒）`);
}

// 2. script and cuts
const clipEnd = (ep.clips || []).reduce((s, c) => s + c.dur, 0);
const script = [];
const cuts = [];
if (ep.style === 'explainer') {
  for (const it of ep.items) {
    const t1 = it.t1 ?? ep.duration;
    if (it.type === 'text' || it.type === 'formula') script.push([it.t0, t1, '画面の文字', it.text.replace(/\[\[|\]\]|\{\{|\}\}/g, '')]);
    if (it.type === 'bubble') script.push([it.t0, t1, '吹き出し', it.text]);
    if (it.type === 'zone') script.push([it.quoteT ?? it.t0, t1, `枠「${it.tag}」`, it.quote]);
  }
  for (const [i, c] of (ep.cuts || []).entries()) cuts.push({ n: i + 1, t0: c.t0, t1: c.t1, what: c.material, role: c.role, narration: c.narration });
} else if (ep.style === 'drama') {
  if (ep.hook) script.push([0, ep.hook.until, '見出し', ep.hook.lines.join('／')]);
  for (const s of ep.subs) {
    const who = (s.who || '') + (s.who && s.tag ? 'の' : '') + (s.tag || '');
    script.push([s.t, s.until, who ? `字幕（${who}）` : '中央のカード', s.text]);
  }
  let t = 0;
  for (const [i, c] of ep.clips.entries()) {
    const src = /\.(jpe?g|png|webp)$/i.test(c.file) ? `写真 ${c.file}（動き: ${c.move || 'in'}${c.dim ? '、ぼかし' : ''}）` : `動画 ${c.file} の ${f1(c.start || 0)}〜${f1((c.start || 0) + c.dur)}秒`;
    cuts.push({ n: i + 1, t0: t, t1: t + c.dur, what: src + (c.placeholder ? '　※仮素材' : ''), role: c.role, want: c.want });
    t += c.dur;
  }
  cuts.push({ n: cuts.length + 1, t0: clipEnd, t1: clipEnd + ep.endDur, what: '最後の画面（文字のみ）', role: '誘導' });
  const E = ep.end || {};
  for (const [k, label] of [['title', 'タイトル'], ['question', '問いかけ'], ['cta', '誘導'], ['note1', '補足'], ['note2', '注記']]) {
    if (E[k]) script.push([clipEnd, clipEnd + ep.endDur, `最後の画面（${label}）`, Array.isArray(E[k]) ? E[k].join('／') : E[k]]);
  }
} else {
  for (const e of ep.events) if (e.text) script.push([e.t, null, { left: '相手', right: '店長', pill: '心の声', date: '日付', stamp: 'スタンプ' }[e.type] || e.type, e.text]);
}
script.sort((a, b) => a[0] - b[0]);

// 3. placeholders and what is unchecked
const placeholders = [];
for (const c of cuts) if (/仮素材/.test(c.what)) placeholders.push(`カット${c.n}（${f1(c.t0)}〜${f1(c.t1)}秒）: ${c.what.replace('　※仮素材', '')}${c.want ? ` → 本番で使いたいもの: ${c.want}` : ''}`);
if (ep.style === 'explainer') placeholders.push('映像素材なし。全編、図と文字だけで作っている');
if (ep.style === 'explainer' && !(ep.audio || []).length && !(ep.voice || []).length) placeholders.push('ナレーションの音声なし。画面の文字のタイミングは読む速さからの仮置き');
if ((ep.voice || []).length) placeholders.push('ナレーションは仮の声（読み上げソフト Open JTalk の機械音声）。本人の声ではない。タイミングはこの声の長さに合わせてある');
if (ep.style === 'drama' && !(ep.audio || []).length && ep.clips.every((c) => c.mute || /\.(jpe?g|png|webp)$/i.test(c.file))) placeholders.push('セリフの音声なし（字幕のみ）');
const section = (md, title) => {
  const m = md.match(new RegExp(`## ${title}\\n([\\s\\S]*?)(\\n## |$)`));
  return m ? m[1].trim() : '';
};
const brief = briefFile && fs.existsSync(briefFile) ? fs.readFileSync(briefFile, 'utf8') : '';
const checked = spawnSync('node', [path.join(__dirname, 'check.js'), video, epFile]).stdout.toString().split('\n').filter((l) => /^(OK|WARNING)/.test(l));

L.push(`# リール試作の見直し資料`, '');
L.push('ChatGPT へ: 以下は Instagram リール（店長向け）の試作です。添付の画像は書き出した動画の1秒・3秒・5秒の画面です。');
L.push('台本とカットの区切りを見て、(1) 冒頭で誰のどんな悩みか伝わるか (2) 持ち帰る行動が1つに絞れているか (3) 映像と字幕の意味がつながっているか (4) 次に直すべき一点、を指摘してください。');
L.push('仮素材と未確認の項目は下に書いてあります。完成品としてではなく、試作として見てください。', '');
L.push('## 動画', `- ファイル: ${path.basename(video)}`, `- 長さ: ${f1(dur)}秒、${vs.width}x${vs.height}`, `- 形式: ${ep.style === 'explainer' ? '図解（図と文字）' : ep.style === 'drama' ? '写真・動画＋字幕' : 'チャット画面'}`, `- 添付画像: ${frames.join('、')}`, '');
L.push('## 添付画像の時点で画面に出ている文字');
for (const t of [1, 3, 5].filter((x) => x < dur)) {
  // a line counts once it has faded in (about 0.15 s) and until it starts to fade out
  const on = script.filter(([t0, t1]) => t >= t0 + 0.15 && (t1 == null || t < t1 - 0.05)).map(([, , kind, text]) => `${kind}「${one(text)}」`);
  // lines still fading in or already fading out are named as such, so the image and the text agree
  const coming = script.filter(([t0]) => t >= t0 - 0.05 && t < t0 + 0.15).map(([, , kind, text]) => `${kind}「${one(text)}」が出てくる途中`);
  const going = script.filter(([, t1]) => t1 != null && t >= t1 - 0.05 && t < t1 + 0.25).map(([, , kind, text]) => `${kind}「${one(text)}」が消えていく途中`);
  const all = [...on, ...coming, ...going];
  L.push(`- ${t}.0秒: ${all.length ? all.join('、') : '文字なし（切り替わりの瞬間）'}`);
}
L.push('');
L.push('## 台本（時刻順）');
for (const [t0, t1, kind, text] of script) L.push(`- ${f1(t0)}${t1 != null ? '〜' + f1(t1) : ''}秒　${kind}: ${one(text)}`);
L.push('');
if (cuts.length) {
  L.push('## カット（開始〜終了）');
  for (const c of cuts) {
    L.push(`- カット${c.n}: ${f1(c.t0)}〜${f1(c.t1)}秒`);
    if (c.narration) L.push(`  - ナレーション（${(ep.voice || []).length ? '仮の声・読み上げソフト' : '未録音'}）: ${c.narration}`);
    L.push(`  - 素材: ${c.what}`);
    if (c.role) L.push(`  - 役割: ${c.role}`);
  }
  L.push('');
}
L.push('## 仮素材・足りないもの');
for (const p of placeholders.length ? placeholders : ['なし']) L.push(`- ${p}`);
L.push('');
L.push('## 確認できていない項目（実際には聞いていない・見ていないもの）');
const unchecked = section(brief, '未確認のこと') || section(brief, '実際には聞いていない・見ていない項目');
L.push(unchecked || '- 音を耳で聞いた確認（BGM・効果音の大きさ、テンポ）\n- Instagram の実際の画面で、ボタンやキャプションと字幕が重ならないか\n- 投稿後の数字（視聴時間・保存・シェア）');
L.push('');
L.push('## 確認したこと（自動チェック）');
for (const l of checked) L.push(`- ${l.replace(/^OK\s+/, 'OK: ').replace(/^WARNING\s+/, '要確認: ')}`);
const done = section(brief, '確認したこと') || section(brief, '技術的に確認した項目');
if (done) L.push('', '## 確認したこと（技術的な確認と目視）', done);
fs.writeFileSync(path.join(outDir, 'review.txt'), L.join('\n') + '\n');
console.log('review pack:', outDir, frames.join(' '));
