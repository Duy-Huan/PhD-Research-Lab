'use strict';
// Dev tool: wrap every Vietnamese UI string literal of frontend/assets/*.js in PL.t(...) and list the keys that still
// need an English entry in frontend/assets/i18n-en.js.
//   node tools/i18n_wrap.js            wrap in place + report missing keys
//   node tools/i18n_wrap.js --check    report only (exit 1 when a Vietnamese literal is not wrapped or has no entry)
const fs = require('node:fs');
const path = require('node:path');

const dir = path.join(__dirname, '..', 'frontend', 'assets');
const VI = /[À-ỹđĐ]/;
const check = process.argv.includes('--check');
const skip = new Set(['i18n.js', 'i18n-en.js']);

function wrapFile(src) {
  let out = '', i = 0, changed = 0;
  const keys = [], raw = [];
  let last = '';  // last significant token char, to tell a regex from a division
  const regexOk = () => !last || /[(,=:[!&|?{};+\-*%<>~^]/.test(last) || /\b(return|typeof|case|in|of)$/.test(out.trimEnd());
  while (i < src.length) {
    const c = src[i], n = src[i + 1];
    if (c === '/' && n === '/') { const e = src.indexOf('\n', i); const j = e < 0 ? src.length : e; out += src.slice(i, j); i = j; continue; }
    if (c === '/' && n === '*') { const j = src.indexOf('*/', i + 2) + 2; out += src.slice(i, j); i = j; continue; }
    if (c === '/' && regexOk()) {
      let j = i + 1, cls = false;
      while (j < src.length && (src[j] !== '/' || cls)) { if (src[j] === '\\') j++; else if (src[j] === '[') cls = true; else if (src[j] === ']') cls = false; j++; }
      j++;
      while (/[a-z]/i.test(src[j] || '')) j++;
      out += src.slice(i, j); i = j; last = '/'; continue;
    }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < src.length && src[j] !== c) { if (src[j] === '\\') j++; j++; }
      const lit = src.slice(i, j + 1);
      const before = out.slice(-5);
      const body = lit.slice(1, -1);
      const isKey = /^\s*:/.test(src.slice(j + 1, j + 4)) && !/\?\s*$/.test(out.slice(-3));
      if (VI.test(body) && before !== 'PL.t(' && !isKey) {
        const val = Function('return ' + lit)();
        out += 'PL.t(' + JSON.stringify(val) + ')'; keys.push(val); raw.push(val); changed++;
      } else {
        if (before === 'PL.t(' && VI.test(body)) keys.push(Function('return ' + lit)());
        out += lit;
      }
      i = j + 1; last = c; continue;
    }
    if (c === '`') {
      // template literal: split into text parts and ${expressions} (nested braces counted)
      let j = i + 1; const parts = [''], exprs = [];
      while (j < src.length && src[j] !== '`') {
        if (src[j] === '\\') { parts[parts.length - 1] += src[j] + src[j + 1]; j += 2; continue; }
        if (src[j] === '$' && src[j + 1] === '{') {
          let depth = 1, k = j + 2;
          while (depth && k < src.length) { if (src[k] === '{') depth++; else if (src[k] === '}') depth--; else if (src[k] === '`') { k = src.indexOf('`', k + 1); } k++; }
          exprs.push(src.slice(j + 2, k - 1)); parts.push(''); j = k; continue;
        }
        parts[parts.length - 1] += src[j]; j++;
      }
      const lit = src.slice(i, j + 1);
      const text = parts.map((p, k) => p + (k < exprs.length ? '{' + k + '}' : '')).join('');
      if (VI.test(parts.join('')) && out.slice(-5) !== 'PL.t(' && !/<[a-z!]/i.test(parts.join(''))) {
        const val = Function('return `' + text.replace(/`/g, '\\`') + '`')();
        out += 'PL.t(' + JSON.stringify(val) + (exprs.length ? ', ' + exprs.join(', ') : '') + ')';
        keys.push(val); raw.push(val); changed++;
      } else out += lit;
      i = j + 1; last = '`'; continue;
    }
    out += c;
    if (!/\s/.test(c)) last = c;
    i++;
  }
  return { out, changed, keys, raw };
}

const en = (() => { const W = { PL: {} }; try { new Function('window', fs.readFileSync(path.join(dir, 'i18n-en.js'), 'utf8'))(W); } catch (e) { /* none yet */ } return W.PL.EN || {}; })();
const all = new Set();
let unwrapped = 0;
for (const f of fs.readdirSync(dir).filter((x) => x.endsWith('.js') && !skip.has(x))) {
  const p = path.join(dir, f);
  const r = wrapFile(fs.readFileSync(p, 'utf8'));
  r.keys.forEach((k) => all.add(k));
  if (r.changed) {
    unwrapped += r.changed;
    if (!check) fs.writeFileSync(p, r.out);
    console.log(`${f}: ${r.changed} string(s) ${check ? 'not wrapped' : 'wrapped'}`);
  }
}
// keys used in index.html data-t attributes
const html = fs.readFileSync(path.join(dir, '..', 'index.html'), 'utf8');
for (const m of html.matchAll(/data-t(?:-title|-placeholder|-aria)?="([^"]+)"/g)) all.add(m[1].replace(/&amp;/g, '&'));
const missing = [...all].filter((k) => !(k in en));
fs.writeFileSync(path.join(require('node:os').tmpdir(), 'phdlab-i18n-missing.json'), JSON.stringify(missing, null, 1));
console.log(`${all.size} keys · ${missing.length} without English entry` + (missing.length ? ` → ${path.join(require('node:os').tmpdir(), 'phdlab-i18n-missing.json')}` : ''));
if (check && (unwrapped || missing.length)) process.exit(1);
