// Renders a reel script to an mp4.
//   node studio/render.mjs <scenes.json> <out.mp4>
// Prints {"duration":..,"coverMs":..} on success. Needs Playwright's Chromium and ffmpeg.
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { checkSpec } from './spec.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
// require() also honours NODE_PATH, which is how a globally installed Playwright is found
const { chromium } = createRequire(import.meta.url)('playwright');
const [specPath, outPath] = process.argv.slice(2);
if (!specPath || !outPath) { console.error('usage: node studio/render.mjs <scenes.json> <out.mp4>'); process.exit(2); }
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
const problems = checkSpec(spec);
if (problems.length) { console.error('script problems:\n- ' + problems.join('\n- ')); process.exit(1); }

const FPS = 30, RATE = 44100;

// Small synthesized sound cues so the reel is not silent: a soft pop per message,
// a low thump for the red label, and a short airy sweep between parts.
function writeWav(file, seconds, events) {
  const n = Math.ceil(seconds * RATE), pcm = new Float32Array(n);
  let seed = 7; const noise = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;
  const put = (t0, len, fn) => { const s = Math.max(0, Math.floor(t0 * RATE)); for (let i = 0; i < len * RATE && s + i < n; i++) pcm[s + i] += fn(i / RATE); };
  for (const e of events) {
    if (e.type === 'pop') put(e.t, 0.09, x => 0.22 * Math.sin(2 * Math.PI * (880 - 2400 * x) * x) * Math.exp(-x * 45));
    if (e.type === 'stamp') put(e.t, 0.22, x => 0.45 * Math.sin(2 * Math.PI * 110 * x) * Math.exp(-x * 18) + 0.12 * noise() * Math.exp(-x * 40));
    if (e.type === 'whoosh') { let lp = 0; put(e.t, 0.35, x => { lp += 0.08 * (noise() - lp); return 0.5 * lp * Math.sin(Math.PI * x / 0.35); }); }
  }
  const buf = Buffer.alloc(44 + n * 2);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write('WAVEfmt ', 8);
  buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(RATE, 24);
  buf.writeUInt32LE(RATE * 2, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, pcm[i])) * 32767), 44 + i * 2);
  fs.writeFileSync(file, buf);
}

const launch = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {};
const browser = await chromium.launch(launch);
try {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(path.join(here, 'template.html')).href);
  await page.evaluate(async () => { await document.fonts.load('900 40px NotoJP'); await document.fonts.load('700 40px NotoJP'); await document.fonts.ready; });
  const plan = await page.evaluate(s => window.setup(s), spec);
  if (plan.total < 12 || plan.total > 40) throw new Error(`reel would be ${plan.total}s; keep scripts between 12 and 40 seconds`);

  fs.mkdirSync(path.dirname(path.resolve(outPath)), { recursive: true });
  const wav = outPath + '.wav';
  writeWav(wav, plan.total, plan.events);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-i', wav, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '20', '-r', String(FPS),
    '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', outPath], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((ok, fail) => ff.on('close', code => code === 0 ? ok() : fail(new Error('ffmpeg exited with ' + code))));

  const frames = Math.ceil(plan.total * FPS);
  let lastKey = null, lastShot = null;
  for (let i = 0; i < frames; i++) {
    const key = await page.evaluate(t => window.renderAt(t), i / FPS);
    if (key !== lastKey || !lastShot) lastShot = await page.screenshot({ type: 'jpeg', quality: 92 });
    lastKey = key;
    if (!ff.stdin.write(lastShot)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await done;
  fs.rmSync(wav, { force: true });
  console.log(JSON.stringify({ duration: plan.total, coverMs: plan.coverMs }));
} finally {
  await browser.close();
}
