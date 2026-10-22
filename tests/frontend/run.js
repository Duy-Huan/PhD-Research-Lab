'use strict';
// Run every frontend test with coverage of frontend/assets/*.js; print uncovered lines / branches / functions; exit 1 on a failing
// test, 2 when coverage is below 100 %.   node tests/frontend/run.js [file.test.js …]
const {spawnSync} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const here = __dirname;
const lcov = path.join(os.tmpdir(), `phdlab-frontend-${process.pid}.lcov`);
const files = process.argv.slice(2).length ? process.argv.slice(2) : fs.readdirSync(here).filter((f) => f.endsWith('.test.js'));
const r = spawnSync(process.execPath, ['--test', '--experimental-test-coverage', '--test-coverage-include=**/frontend/assets/**',
  '--test-reporter=spec', '--test-reporter-destination=stdout', '--test-reporter=lcov', `--test-reporter-destination=${lcov}`, ...files],
{cwd: here, stdio: ['ignore', 'pipe', 'inherit'], encoding: 'utf8'});
const out = r.stdout || '';
process.stdout.write(out.split('\n').filter((l) => !/^ℹ\s+(\.\.|frontend|assets)\s/.test(l)).join('\n'));
let missing = 0, file = '';
const gaps = {};
const measured = new Set();
const functions = {};
for (const line of fs.readFileSync(lcov, 'utf8').split(/\r?\n/)) {
  if (line.startsWith('SF:')) { file = path.basename(line.slice(3)); measured.add(file); }
  let fn = /^FN:(\d+),(.+)$/.exec(line);
  if (fn) (functions[file + ':' + fn[2]] ||= []).push(fn[1]);
  fn = /^FNDA:(\d+),(.+)$/.exec(line);
  if (fn) {
    const location = functions[file + ':' + fn[2]].shift();
    if (fn[1] === '0') { (gaps[file] = gaps[file] || new Set()).add('F' + location); missing++; }
  }
  let m = /^DA:(\d+),0$/.exec(line);
  if (m) { (gaps[file] = gaps[file] || new Set()).add('L' + m[1]); missing++; }
  m = /^BRDA:(\d+),\d+,\d+,(?:0|-)$/.exec(line);
  if (m) { (gaps[file] = gaps[file] || new Set()).add('B' + m[1]); missing++; }
}
for (const f of fs.readdirSync(path.resolve(here, '../../frontend/assets')).filter(f => f.endsWith('.js'))) {
  if (!measured.has(f)) { console.log('unmeasured first-party script: ' + f); missing++; }
}
const evidence = path.resolve(here, '../../artifacts/ui-refinement');
fs.mkdirSync(evidence, {recursive:true});
fs.copyFileSync(lcov, path.join(evidence, 'frontend.lcov'));
fs.rmSync(lcov, {force: true});
for (const [f, s] of Object.entries(gaps)) console.log(`uncovered ${f}: ${[...s].join(' ')}`);
if (r.status) process.exit(1);
if (missing) { console.log(`frontend coverage incomplete: ${missing} line/branch/function gaps`); process.exit(2); }
console.log('frontend coverage: 100 % lines, branches and functions of all frontend/assets JavaScript');
