// Checks one or more reel scripts without rendering them.
//   node studio/check.mjs queue/<id>/scenes.json [...]
import fs from 'node:fs';
import { checkSpec } from './spec.mjs';

let bad = 0;
for (const file of process.argv.slice(2)) {
  let problems;
  try { problems = checkSpec(JSON.parse(fs.readFileSync(file, 'utf8'))); }
  catch (e) { problems = ['cannot read: ' + e.message]; }
  if (problems.length) { bad++; console.log(`NG ${file}\n- ${problems.join('\n- ')}`); }
  else console.log(`OK ${file}`);
}
process.exit(bad ? 1 : 0);
