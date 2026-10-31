// Checks a finished reel before it is booked, and writes a contact sheet of its frames next to it.
//   node check.js video.mp4 [episodes/<id>.json]
// Prints OK / WARNING lines and exits with 2 when there is a warning.
const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');

const [video, epFile] = process.argv.slice(2);
const warn = [], ok = [];
const check = (cond, good, bad) => (cond ? ok : warn).push(cond ? good : bad);
const ffmpegLog = (...vf) => spawnSync('ffmpeg', ['-v', 'info', '-i', video, ...vf, '-f', 'null', '-']).stderr.toString();

const info = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries',
  'format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate', '-of', 'json', video]).toString());
const v = info.streams.find((s) => s.codec_type === 'video');
const a = info.streams.find((s) => s.codec_type === 'audio');
const dur = Number(info.format.duration);
const mb = Number(info.format.size) / 1e6;

check(v && v.width === 1080 && v.height === 1920, 'size 1080x1920', `size is ${v && v.width}x${v && v.height}, not 1080x1920`);
check(v && v.r_frame_rate === '30/1', '30 fps', `frame rate is ${v && v.r_frame_rate}, not 30`);
check(dur >= 10 && dur <= 60, `length ${dur.toFixed(1)}s`, `length ${dur.toFixed(1)}s is outside 10-60s`);
check(mb < 90, `file ${mb.toFixed(1)} MB`, `file is ${mb.toFixed(1)} MB; GitHub refuses files over 100 MB`);
check(!!a, 'has sound', 'no sound track');

if (a) {
  const loud = ffmpegLog('-vn', '-af', 'ebur128=peak=true');
  const lufs = Number((loud.match(/I:\s+(-?[\d.]+) LUFS/g) || []).pop()?.match(/-?[\d.]+/)[0]);
  const peak = Number((loud.match(/Peak:\s+(-?[\d.]+) dBFS/g) || []).pop()?.match(/-?[\d.]+/)[0]);
  check(lufs >= -16.5 && lufs <= -11.5, `loudness ${lufs} LUFS`, `loudness ${lufs} LUFS; reels should be near -14`);
  check(!(peak > -0.5), `peak ${peak} dBFS`, `peak ${peak} dBFS clips`);
  const silences = [...ffmpegLog('-vn', '-af', 'silencedetect=n=-45dB:d=3').matchAll(/silence_start: ([\d.]+)/g)].map((m) => Number(m[1]));
  check(!silences.length, 'no long silence', `silent for 3s or more from ${silences.map((s) => s.toFixed(1) + 's').join(', ')}`);
}

const crop = [...ffmpegLog('-an', '-vf', 'cropdetect=limit=24:round=2:reset=0').matchAll(/crop=(\d+):(\d+)/g)].pop();
check(!crop || (Number(crop[1]) >= 1076 && Number(crop[2]) >= 1916), 'no black bars', `black bars: the picture is only ${crop && crop[1]}x${crop && crop[2]}`);
const blacks = [...ffmpegLog('-an', '-vf', 'blackdetect=d=0.4:pix_th=0.08').matchAll(/black_start:([\d.]+)/g)].map((m) => Number(m[1]));
check(!blacks.length, 'no black frames', `black screen at ${blacks.map((s) => s.toFixed(1) + 's').join(', ')}`);

if (epFile) {
  const ep = JSON.parse(fs.readFileSync(epFile, 'utf8'));
  // an explainer's readable lines are its items; a drama's are its subtitles
  const subs = ep.style === 'explainer'
    ? ep.items.filter((it) => it.text || it.quote).map((it) => ({ t: it.quoteT ?? it.t0, until: it.t1 ?? ep.duration, text: (it.quote || it.text).replace(/\[\[|\]\]|\{\{|\}\}/g, '') }))
    : ep.subs || [];
  const first = Math.min(ep.hook ? 0 : Infinity, ...subs.map((s) => s.t));
  check(first <= 1, 'something to read within the first second', `nothing on screen until ${first}s; the first second decides whether people stay`);
  for (const s of subs) {
    const lines = s.text.split('\n');
    const chars = s.text.replace(/\n/g, '').length;
    if (lines.length > 2) warn.push(`more than 2 lines: ${s.text.replace(/\n/g, '/')}`);
    for (const l of lines) if (l.length > 15) warn.push(`line longer than 15 characters: ${l}`);
    if (s.until - s.t < 0.15 * chars + 0.5) warn.push(`shown too briefly to read (${(s.until - s.t).toFixed(1)}s for ${chars} characters): ${s.text.replace(/\n/g, '/')}`);
  }
  if (ep.style === 'drama') check(!!ep.end && !!ep.end.cta, 'end card leads somewhere', 'no end card call to action');
}

// contact sheet: one frame every 2 seconds, six to a row
const sheet = video.replace(/\.mp4$/, '') + '.sheet.png';
const n = Math.ceil(dur / 2);
execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', video, '-vf', `fps=1/2,scale=216:-1,tile=6x${Math.ceil(n / 6)}`, '-frames:v', '1', sheet]);

for (const o of ok) console.log('OK     ', o);
for (const w of warn) console.log('WARNING', w);
console.log('sheet  ', sheet);
process.exit(warn.length ? 2 : 0);
