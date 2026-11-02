// Checks a reel script (scenes.json) before it is rendered or queued.
// Returns a list of problems; an empty list means the script is usable.
const plain = s => String(s ?? '').replace(/\*/g, '');
const width = s => [...plain(s)].reduce((n, c) => n + (c.charCodeAt(0) < 0x2000 ? 0.56 : 1), 0);

export function checkSpec(spec) {
  const errors = [];
  const need = (ok, msg) => { if (!ok) errors.push(msg); };
  need(spec && typeof spec === 'object', 'script is not a JSON object');
  if (errors.length) return errors;

  need(Array.isArray(spec.hook) && spec.hook.length >= 1 && spec.hook.length <= 3, 'hook: 1-3 lines');
  (spec.hook || []).forEach((l, i) => need(width(l) <= 13, `hook[${i}] is too long (${width(l).toFixed(1)} > 13 full-width chars): ${plain(l)}`));
  need((spec.hook || []).some(l => /\*[^*]+\*/.test(l)), 'hook: mark the key words with *...* so they get the yellow highlight');

  const c = spec.chat || {};
  need(typeof c.title === 'string' && c.title.length > 0 && width(c.title) <= 14, 'chat.title: who the chat is with, up to 14 chars');
  need(typeof c.ng === 'string' && width(c.ng) <= 12 && c.ng.length > 0, 'chat.ng: the red label, up to 12 chars');
  need(!c.fixLabel || width(c.fixLabel) <= 10, 'chat.fixLabel: up to 10 chars');
  const msgs = (list, name, min, max) => {
    need(Array.isArray(list) && list.length >= min && list.length <= max, `${name}: ${min}-${max} messages`);
    (list || []).forEach((m, i) => {
      need(['me', 'them', 'divider'].includes(m.who), `${name}[${i}].who must be me, them or divider`);
      need(typeof m.text === 'string' && m.text.length > 0, `${name}[${i}].text is empty`);
      const lines = String(m.text || '').split('\n');
      need(lines.length <= 4, `${name}[${i}] has more than 4 lines`);
      lines.forEach(l => need(width(l) <= 15.5, `${name}[${i}] line too long for a bubble (${width(l).toFixed(1)} > 15.5): ${l}`));
    });
  };
  msgs(c.problem, 'chat.problem', 2, 5);
  msgs(c.fix, 'chat.fix', 1, 4);
  const ngAfter = c.ngAfter ?? 2;
  need(Number.isInteger(ngAfter) && ngAfter >= 1 && ngAfter <= 2, 'chat.ngAfter: 1 or 2, so the red label shows within the first 1.5 seconds');
  need(c.problem?.[0]?.who !== 'divider', 'chat.problem[0] must be a message (it is on screen from the first frame)');

  const o = spec.outro || {};
  need(Array.isArray(o.title) && o.title.length >= 1 && o.title.length <= 3, 'outro.title: 1-3 lines');
  (o.title || []).forEach((l, i) => need(width(l) <= 12, `outro.title[${i}] too long (${width(l).toFixed(1)} > 12): ${plain(l)}`));
  need(!o.question || plain(o.question).length <= 60, 'outro.question: up to 60 chars');
  need(!o.cta || width(o.cta) <= 16, 'outro.cta: up to 16 chars');
  need(!o.save || width(o.save) <= 22, 'outro.save: up to 22 chars');
  return errors;
}
