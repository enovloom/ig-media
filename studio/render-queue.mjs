// Renders every queued post that has a script (scenes.json) but no up-to-date video.
//   node studio/render-queue.mjs        (run from the repository root)
// For each one it writes media/<id>/video.mp4, records queue/<id>/render.json, sets the
// cover frame in post.json, and approves the post if it asked for that with "autoApprove".
// Posts that are already published are left alone.
import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const studio = path.join(root, 'studio');
const queue = path.join(root, 'queue');
const read = f => fs.readFileSync(f, 'utf8');
const state = fs.existsSync(path.join(queue, 'state.json')) ? JSON.parse(read(path.join(queue, 'state.json')).replace(/^﻿/, '')) : {};
const engine = ['template.html', 'render.mjs', 'spec.mjs'].map(f => read(path.join(studio, f))).join('\n');

const rendered = [], failed = [];
for (const id of fs.readdirSync(queue).sort()) {
  const dir = path.join(queue, id), scenes = path.join(dir, 'scenes.json');
  if (!fs.existsSync(scenes)) continue;
  if (['published', 'publishing'].includes(state[id]?.status)) continue;
  const hash = crypto.createHash('sha256').update(read(scenes) + engine).digest('hex').slice(0, 16);
  const recordFile = path.join(dir, 'render.json');
  const record = fs.existsSync(recordFile) ? JSON.parse(read(recordFile)) : {};
  const video = path.join(root, 'media', id, 'video.mp4');
  if (record.hash === hash && !record.error && fs.existsSync(video)) continue;

  console.log(`rendering ${id}`);
  try {
    const out = execFileSync('node', [path.join(studio, 'render.mjs'), scenes, video], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    const info = JSON.parse(out.trim().split('\n').pop());
    const postFile = path.join(dir, 'post.json');
    const post = JSON.parse(read(postFile));
    post.type = 'reel';
    post.media = ['video.mp4'];
    post.thumbOffsetMs = info.coverMs;
    if (post.autoApprove) post.approved = true;
    fs.writeFileSync(postFile, JSON.stringify(post, null, 2) + '\n');
    fs.writeFileSync(recordFile, JSON.stringify({ hash, duration: info.duration, coverMs: info.coverMs, renderedAt: new Date().toISOString() }, null, 2) + '\n');
    rendered.push(id);
  } catch (e) {
    const msg = String(e.stderr || e.message).trim().slice(0, 2000);
    console.error(`failed ${id}: ${msg}`);
    fs.writeFileSync(recordFile, JSON.stringify({ hash, error: msg, failedAt: new Date().toISOString() }, null, 2) + '\n');
    failed.push(id);
  }
}
console.log(`rendered: ${rendered.join(', ') || 'none'}`);
if (failed.length) { console.log(`failed: ${failed.join(', ')}`); process.exit(1); }
