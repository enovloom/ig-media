// Renders scene.json into a 1080x1920 30fps reel.
//   node render.js <scene.json> --stills 0.6,9,20,33   -> PNG stills for checking the layout
//   node render.js <scene.json> <audio.wav> <out.mp4>  -> full video
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

(async () => {
  const [sceneFile, a2, a3] = process.argv.slice(2);
  const scene = JSON.parse(fs.readFileSync(sceneFile, 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto('file://' + path.join(__dirname, 'template.html'));
  await page.evaluate(async (s) => { await document.fonts.load('900 74px NSJ'); await document.fonts.load('700 44px NSJ'); await document.fonts.load('500 26px NSJ'); init(s); await document.fonts.ready; }, scene);

  if (a2 === '--stills') {
    for (const t of a3.split(',').map(Number)) {
      await page.evaluate((x) => render(x), t);
      await page.screenshot({ path: path.join(path.dirname(sceneFile), `still_${t}.png`) });
    }
    await browser.close();
    return;
  }

  const [audio, out] = [a2, a3];
  const fps = scene.fps, n = Math.round(scene.duration * fps);
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
    '-r', String(fps), '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  let lastKey = null, lastBuf = null;
  for (let i = 0; i < n; i++) {
    const key = await page.evaluate((x) => render(x), i / fps);
    if (key !== lastKey) { lastBuf = await page.screenshot({ type: 'jpeg', quality: 95 }); lastKey = key; }
    if (!ff.stdin.write(lastBuf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 150 === 0) console.log(`frame ${i}/${n}`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  await browser.close();
  console.log('done', out);
})();
