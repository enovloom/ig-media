// Finishes a reel from video clips or photos: cuts, subtitles, hook title, end card, sound effects and music.
//   node drama.js episodes/<id>.json --prompts            -> the clip prompts with the cast filled in
//   node drama.js episodes/<id>.json <clips dir> <out.mp4> -> the finished 1080x1920 reel
const { chromium } = require('playwright');
const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const [epFile, a2, a3] = process.argv.slice(2);
const ep = JSON.parse(fs.readFileSync(epFile, 'utf8'));
const fill = (p) => p.replace(/\[(\w+)\]/g, (_, k) => ep.cast[k]).replace(/(^|[.!?] )([a-z])/g, (_, a, b) => a + b.toUpperCase());
if (a2 === '--prompts') {
  for (const c of ep.clips.filter((x) => x.prompt)) console.log(`--- ${c.file}` + (c.refs ? `  (reference images: ${c.refs.join(', ')})` : '') + `\n${fill(c.prompt)}\n`);
  process.exit(0);
}

// Veo sometimes letterboxes a 9:16 clip with pure black bars; this finds the picture inside them.
// A clip can set "crop" ("w:h:x:y") by hand when the scene itself is very dark at the edges.
const isPhoto = (file) => /\.(jpe?g|png|webp)$/i.test(file);

// A photo becomes a slow camera move. It is worked on at twice the output size so the move does not jitter.
const MOVES = {
  none: ['1', 'CX', 'CY'],
  in: ['1+0.12*P', 'CX', 'CY'],
  out: ['1.12-0.12*P', 'CX', 'CY'],
  left: ['1.12', '(iw-iw/zoom)*(1-P)', 'CY'],
  right: ['1.12', '(iw-iw/zoom)*P', 'CY'],
  up: ['1.12', 'CX', '(ih-ih/zoom)*(1-P)'],
  down: ['1.12', 'CX', '(ih-ih/zoom)*P'],
};
const photoChain = (i, c, fps) => {
  const frames = Math.round(c.dur * fps);
  const P = `(on/${Math.max(1, frames - 1)})`;
  const [z, x, y] = (MOVES[c.move || 'in'] || MOVES.in).map((e) => e.replaceAll('P', P).replace('CX', '(iw-iw/zoom)/2').replace('CY', '(ih-ih/zoom)/2'));
  // fit "blur" keeps a landscape photo whole over a blurred copy of itself instead of cropping it to the 9:16 frame
  const base = c.fit === 'blur'
    ? `[${i}:v]split[pb${i}][pf${i}];[pb${i}]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,boxblur=40:2,eq=brightness=-0.12[pbb${i}];` +
      `[pf${i}]scale=2160:3840:force_original_aspect_ratio=decrease[pff${i}];[pbb${i}][pff${i}]overlay=(W-w)/2:(H-h)/2`
    : `[${i}:v]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840:(iw-2160)*${c.focusX ?? 0.5}:(ih-3840)*${c.focusY ?? 0.5}` +
      // dim blurs and darkens the photo so a text card on top of it reads as the subject
      (c.dim ? ',boxblur=24:2,eq=brightness=-0.18' : '');
  // the photo comes in as a looped stream of the clip's length and zoompan makes one frame from each (d=1):
  // a single still with d=frames ends early when tpad follows it
  return `${base},setsar=1,zoompan=z='${z}':x='${x}':y='${y}':d=1:s=1080x1920:fps=${fps},format=yuv420p`;
};

const pictureArea = (file, c) => {
  if (c.crop) return c.crop;
  const log = spawnSync('ffmpeg', ['-v', 'info', '-ss', String(c.start || 0), '-t', String(c.dur), '-i', file,
    '-vf', 'cropdetect=limit=24:round=2:reset=0', '-f', 'null', '-']).stderr.toString();
  const m = [...log.matchAll(/crop=(\d+:\d+:\d+:\d+)/g)].pop();
  return m ? m[1] : null;
};

(async () => {
  const [clipsDir, out] = [a2, a3];
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'drama-'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto('file://' + path.join(__dirname, 'drama.html'));
  await page.evaluate(async () => { for (const f of ['900 58px NSJ', '700 30px NSJ', '500 26px NSJ']) await document.fonts.load(f); });
  const warnings = [];
  const layer = async (l, name) => {
    await page.evaluate(([e, x]) => show(e, x), [ep, l]);
    for (const t of await page.evaluate(() => overflow())) warnings.push(`text runs off the frame: ${t}`);
    const f = path.join(tmp, name);
    await page.screenshot({ path: f, omitBackground: true });
    return f;
  };
  const clipEnd = ep.clips.reduce((s, c) => s + c.dur, 0);
  const total = clipEnd + ep.endDur;
  // each overlay is a still image shown from t0 to t1, faded in and out
  const overlays = [{ file: await layer('frame', 'frame.png'), t0: 0, t1: clipEnd, fade: 0 }];
  if (ep.hook) overlays.push({ file: await layer('hook', 'hook.png'), t0: 0, t1: ep.hook.until, fade: 0.25, noFadeIn: true });
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
    const photo = isPhoto(file);
    if (photo) args.push('-loop', '1', '-framerate', String(ep.fps), '-t', String(c.dur));
    args.push('-i', file);
    const hasAudio = !photo && execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', file]).toString().trim() !== '';
    const last = i === n - 1;
    const start = c.start || 0;
    let chain;
    if (photo) {
      chain = photoChain(i, c, ep.fps);
    } else {
      const area = pictureArea(file, c);
      // focusX/focusY pick which part survives when the picture is cropped to fill the frame (0 = left/top, 1 = right/bottom)
      const fx = c.focusX ?? 0.5, fy = c.focusY ?? 0.5;
      chain = `[${i}:v]trim=start=${start}:duration=${c.dur},setpts=PTS-STARTPTS,fps=${ep.fps},` + (area ? `crop=${area},` : '') +
        `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:(iw-1080)*${fx}:(ih-1920)*${fy},setsar=1,format=yuv420p`;
    }
    f.push(chain + (c.fadeIn ? `,fade=t=in:st=0:d=${c.fadeIn}` : '') + (last ? `,tpad=stop_mode=clone:stop_duration=${ep.endDur}` : '') + `[v${i}]`);
    // mute drops the clip's own sound, e.g. when the model added voices the prompt asked it not to
    const src = hasAudio && !c.mute ? `[${i}:a]atrim=start=${start}:duration=${c.dur},asetpts=PTS-STARTPTS,aresample=48000` : `anullsrc=r=48000:cl=stereo,atrim=duration=${c.dur}`;
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
  // extra sounds such as a voice memo: { "file": "voice.m4a", "t": 1.2, "gain": 1 } in "audio", files next to the clips
  const extra = (ep.audio || []).map((a, k) => {
    args.push('-i', path.join(clipsDir, a.file));
    f.push(`[${bgmIdx + 1 + k}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=${a.gain ?? 1},adelay=${Math.round(a.t * 1000)}:all=1[x${k}]`);
    return `[x${k}]`;
  });
  // everything is brought to -14 LUFS, the loudness Instagram plays reels at
  f.push(`[amb]volume=0.8[amb2];[${bgmIdx}:a]volume=0.55[bg];[amb2][bg]${extra.join('')}amix=inputs=${2 + extra.length}:normalize=0:duration=first,` +
    `afade=t=out:st=${(total - 0.8).toFixed(3)}:d=0.8,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]`);
  args.push('-filter_complex', f.join(';'), '-map', `[${cur}]`, '-map', '[aout]', '-t', String(total),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(ep.fps),
    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out);
  execFileSync('ffmpeg', args, { stdio: 'inherit' });
  fs.rmSync(tmp, { recursive: true, force: true });
  for (const w of warnings) console.log('WARNING', w);
  console.log('done', out, total.toFixed(1) + 's');
})();
