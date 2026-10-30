// Finishes a short drama reel from generated clips: cuts, subtitles, hook title, end card and music.
//   node drama.js episodes/<id>.json --prompts            -> the clip prompts with the cast filled in
//   node drama.js episodes/<id>.json <clips dir> <out.mp4> -> the finished 1080x1920 reel
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const [epFile, a2, a3] = process.argv.slice(2);
const ep = JSON.parse(fs.readFileSync(epFile, 'utf8'));
const fill = (p) => p.replace(/\[(\w+)\]/g, (_, k) => ep.cast[k]).replace(/(^|[.!?] )([a-z])/g, (_, a, b) => a + b.toUpperCase());
if (a2 === '--prompts') {
  for (const c of ep.clips) console.log(`--- ${c.file}` + (c.refs ? `  (reference images: ${c.refs.join(', ')})` : '') + `\n${fill(c.prompt)}\n`);
  process.exit(0);
}

(async () => {
  const [clipsDir, out] = [a2, a3];
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'drama-'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto('file://' + path.join(__dirname, 'drama.html'));
  await page.evaluate(async () => { for (const f of ['900 58px NSJ', '700 30px NSJ', '500 26px NSJ']) await document.fonts.load(f); });
  const layer = async (l, name) => {
    await page.evaluate(([e, x]) => show(e, x), [ep, l]);
    const f = path.join(tmp, name);
    await page.screenshot({ path: f, omitBackground: true });
    return f;
  };
  const clipEnd = ep.clips.reduce((s, c) => s + c.dur, 0);
  const total = clipEnd + ep.endDur;
  // each overlay is a still image shown from t0 to t1, faded in and out
  const overlays = [{ file: await layer('frame', 'frame.png'), t0: 0, t1: clipEnd, fade: 0 }];
  overlays.push({ file: await layer('hook', 'hook.png'), t0: 0, t1: ep.hook.until, fade: 0.25, noFadeIn: true });
  for (const [i, s] of ep.subs.entries()) overlays.push({ file: await layer(s, `sub${i}.png`), t0: s.t, t1: s.until, fade: 0.15 });
  overlays.push({ file: await layer('end', 'end.png'), t0: clipEnd, t1: total, fade: 0.5, noFadeOut: true });
  await browser.close();

  const bgm = path.join(tmp, 'bgm.wav');
  execFileSync('python3', [path.join(__dirname, 'audio.py'), epFile, bgm]);

  const args = ['-v', 'error', '-y'];
  const f = [];
  const n = ep.clips.length;
  for (const [i, c] of ep.clips.entries()) {
    const file = path.join(clipsDir, c.file);
    args.push('-i', file);
    const hasAudio = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', file]).toString().trim() !== '';
    const last = i === n - 1;
    f.push(`[${i}:v]trim=duration=${c.dur},setpts=PTS-STARTPTS,fps=${ep.fps},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,format=yuv420p` +
      (c.fadeIn ? `,fade=t=in:st=0:d=${c.fadeIn}` : '') + (last ? `,tpad=stop_mode=clone:stop_duration=${ep.endDur}` : '') + `[v${i}]`);
    const src = hasAudio ? `[${i}:a]atrim=duration=${c.dur},asetpts=PTS-STARTPTS,aresample=48000` : `anullsrc=r=48000:cl=stereo,atrim=duration=${c.dur}`;
    f.push(`${src},aformat=sample_fmts=fltp:channel_layouts=stereo` + (last ? `,apad=pad_dur=${ep.endDur}` : '') + `[a${i}]`);
  }
  f.push(ep.clips.map((_, i) => `[v${i}][a${i}]`).join('') + `concat=n=${n}:v=1:a=1[base][amb]`);
  let cur = 'base';
  for (const [k, o] of overlays.entries()) {
    const idx = n + k, d = o.t1 - o.t0;
    args.push('-loop', '1', '-framerate', String(ep.fps), '-t', String(d), '-i', o.file);
    let chain = `[${idx}:v]format=rgba`;
    if (o.fade && !o.noFadeIn) chain += `,fade=t=in:st=0:d=${o.fade}:alpha=1`;
    if (o.fade && !o.noFadeOut) chain += `,fade=t=out:st=${(d - o.fade).toFixed(3)}:d=${o.fade}:alpha=1`;
    f.push(`${chain},setpts=PTS-STARTPTS+${o.t0}/TB[o${k}]`);
    f.push(`[${cur}][o${k}]overlay=eof_action=pass:enable='between(t,${o.t0},${o.t1})'[c${k}]`);
    cur = `c${k}`;
  }
  const bgmIdx = n + overlays.length;
  args.push('-i', bgm);
  f.push(`[amb]volume=0.8[amb2];[${bgmIdx}:a]volume=0.55[bg];[amb2][bg]amix=inputs=2:normalize=0:duration=first,afade=t=out:st=${(total - 0.8).toFixed(3)}:d=0.8[aout]`);
  args.push('-filter_complex', f.join(';'), '-map', `[${cur}]`, '-map', '[aout]', '-t', String(total),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(ep.fps),
    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out);
  execFileSync('ffmpeg', args, { stdio: 'inherit' });
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log('done', out, total.toFixed(1) + 's');
})();
