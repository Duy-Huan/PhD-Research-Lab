"""Actual container filesystem/network canaries; optional bounded Codex inference."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROBE = r"""
const fs=require('fs'),net=require('net'),http=require('http');
const results={};
function blocked(path,write=false){try{write?fs.writeFileSync(path,'CANARY'):fs.readFileSync(path);return false}catch(e){return ['ENOENT','EACCES','EROFS','EPERM'].includes(e.code)}}
results.source_unmounted=blocked('/host/backend/app.py')&&blocked('/mnt/d/git-repo/PhD-Research-Lab/backend/app.py');
results.system_readonly=blocked('/opt/phdlab/unwanted-write',true);
results.context_readonly=blocked('/context/unwanted-write',true);
results.context_readable=fs.readFileSync('/context/context.md','utf8').length>0;
fs.writeFileSync('/workspace/own-write.txt','OWN');
results.workspace_writable=fs.readFileSync('/workspace/own-write.txt','utf8')==='OWN';
async function direct(){return new Promise(resolve=>{const s=net.connect({host:'1.1.1.1',port:443});s.setTimeout(1000);s.on('connect',()=>{s.destroy();resolve(false)});s.on('error',()=>resolve(true));s.on('timeout',()=>{s.destroy();resolve(true)})})}
async function denied(){return new Promise(resolve=>{const r=http.request({host:'127.0.0.1',port:3128,method:'CONNECT',path:'127.0.0.1:8771'});r.on('connect',(res,s)=>{s.destroy();resolve(res.statusCode===403)});r.on('error',()=>resolve(false));r.setTimeout(3000,()=>{r.destroy();resolve(false)});r.end()})}
(async()=>{results.direct_network_blocked=await direct();results.private_proxy_denied=await denied();fs.writeFileSync('/workspace/containment-results.json',JSON.stringify(results));console.log(JSON.stringify(results));process.exit(Object.values(results).every(Boolean)?0:2)})()
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--infer', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / 'output/playwright'):
        parser.error('Probe data must remain in output/playwright')
    out.mkdir(parents=True, exist_ok=True)
    os.environ['PHDLAB_DATA_DIR'] = str(out / 'data')
    from backend.providers.isolated_cli import prepare, run
    prepared = prepare('codex')
    report = {'mode': 'INTEGRATION_OS_CONTAINER', 'preparation': prepared, 'status': 'BLOCKED'}
    if prepared['state'] == 'PREPARED':
        plan = Path(prepared['plan'])
        code = run(plan, interactive=False, command=['node', '-e', PROBE])
        results = json.loads((Path(prepared['cwd']) / 'containment-results.json').read_text('utf-8'))
        report.update(exit_code=code, assertions=results, status='PASSED' if code == 0 and all(results.values()) else 'FAILED')
        if args.infer and report['status'] == 'PASSED':
            inference = run(plan, interactive=False, command=['codex', 'exec', '--skip-git-repo-check', '--sandbox', 'read-only',
                '--output-last-message', '/workspace/native-answer.txt', 'Reply with exactly OK. Do not use tools.'])
            answer_file = Path(prepared['cwd']) / 'native-answer.txt'
            answer = answer_file.read_text('utf-8').strip() if answer_file.is_file() else ''
            report['live_inference'] = {'provider': 'codex', 'exit_code': inference, 'answer': answer, 'passed': inference == 0 and answer == 'OK'}
            if not report['live_inference']['passed']:
                report['status'] = 'FAILED'
    (out / 'report.json').write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}))
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
