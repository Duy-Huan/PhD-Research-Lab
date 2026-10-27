'use strict';
const {assess,qualifiedErrors}=require('./automerge.cjs');
try {
  const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
  const reasons=(input.operation==='qualification'?qualifiedErrors:assess)(input.snapshot);
  process.stdout.write(JSON.stringify({decision:reasons.length?'BLOCKED':'ELIGIBLE',reasons})+'\n');
  process.exitCode=reasons.length?2:0;
} catch {
  process.stdout.write(JSON.stringify({decision:'BLOCKED',reasons:['Malformed promotion snapshot']})+'\n');
  process.exitCode=2;
}
