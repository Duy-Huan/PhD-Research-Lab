"""Single development verification entrypoint. No runtime research-agent imports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

from .contracts import validate_contract, validate_tdd
from .evidence import aggregate, fingerprints, RepairBudget
from .selection import changed_files, select

ROOT = Path(__file__).resolve().parents[2]


def identity(root: Path) -> dict:
    """Hash source, tests, contracts, policy, runner and dependency inputs, including dirty files."""
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root)
    prefixes = ('backend/', 'frontend/src/', 'frontend/e2e/', 'devtools/', 'scripts/', 'tools/',
                'tests/', '.github/', '.githooks/', 'docs/qa/contracts/', '.codex/', '.agents/', '.claude/', '.gemini/', 'skills/', 'agent/')
    exact = {'requirements.txt', 'requirements-dev.txt', 'requirements-ci.lock', 'requirements-uat.in', 'requirements-uat.lock', '.coveragerc', '.gitignore', '.gitattributes',
             'pyproject.toml','pytest.ini','tox.ini','ruff.toml','AGENTS.md',
             'agent/AGENT.md', 'agent/DEVELOPMENT_WORKFLOW.md', 'agent/UAT.md', 'agent/CLI_COMPATIBILITY.md',
             'CLAUDE.md', 'GEMINI.md', 'skills/SOURCES.json', 'docs/qa/KNOWN_ISSUES_BASELINE.json',
             'docs/qa/CRITICAL_SOFTWARE_CHECKS.json','agent/CI_REPAIR_SUPERVISOR.md','agent/CI_CD_AUTOMATION.md',
             'agent/DEV_QA_MAIN.md','docs/quality/ZERO_FAKE_TESTING_POLICY.md','docs/quality/REGRESSION_PREVENTION.md',
             'frontend/package.json', 'frontend/package-lock.json', 'frontend/vite.config.ts',
             'frontend/playwright.config.ts', 'start.py'}
    files = {}
    for name in sorted(set(paths.decode('utf-8').split('\0'))):
        path = root / name
        generated=name.startswith(('frontend/dist/','frontend/coverage/','frontend/node_modules/',
                                   'output/','artifacts/','qa/live_e2e/runs/','docs/qa/evidence/'))
        operational = name in ('agent/STATE.md', 'agent/PLAN.md') or name.startswith(('agent/history/', 'agent/repair-ledgers/'))
        if name and not generated and not operational and (name.startswith(prefixes) or name.startswith('frontend/') or name in exact
                or path.suffix in ('.py','.sh','.cmd','.bat','.ps1')):
            # Absence is represented by an absent key, regardless of whether deletion is staged.
            if not path.is_file():continue
            raw = path.read_bytes()
            if path.suffix in ('.py','.ts','.tsx','.js','.mjs','.cjs','.json','.md','.yml','.yaml','.toml','.lock','.txt','.in','.ini','.cfg','.css','.html','.svg','.sh','.cmd','.bat','.ps1') or path.name in ('.coveragerc','.gitignore','.gitattributes','LICENSE','UPSTREAM_LICENSE','Dockerfile'):
                raw = raw.replace(b'\r\n',b'\n')
            files[name] = hashlib.sha256(raw).hexdigest()
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {'sha256': digest, 'files': files, 'normalization':'LF for declared text source types; binary bytes unchanged'}


def run_command(name: str, argv: list[str], cwd: Path, out: Path, timeout: int = 1200) -> dict:
    started = time.monotonic(); logfile = out / (name + '.log')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PHDLAB_QA_OFFLINE='1', CI='1')
    with logfile.open('wb') as log:
        try:
            result = subprocess.run(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout, env=env, shell=False)
            code, reason = result.returncode, None
        except subprocess.TimeoutExpired:
            code, reason = 124, 'Verification process timeout; inspect raw log'
        except OSError as exc:
            code, reason = 127, type(exc).__name__ + ': ' + str(exc)
    return {'id': name, 'status': 'PASS' if code == 0 else 'FAIL', 'exit_code': code,
            'command': argv, 'cwd': str(cwd), 'seconds': round(time.monotonic() - started, 3),
            'log': str(logfile), 'details': reason}


def validate_live(path: Path | None, source: str, head: str) -> list[str]:
    if not path or not path.is_file():
        return ['Real 2D, 3D, CLI, all-provider and experiment/paper evidence is not supplied']
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
        errors = []
        if manifest.get('source_sha256') != source or manifest.get('head_sha') != head:
            errors.append('Live evidence belongs to a different source or commit')
        for layer in ('2d', '3d', 'cli', 'providers', 'scientific'):
            record = manifest.get('layers', {}).get(layer, {})
            if record.get('status') != 'PASS' or record.get('mode') not in ('REAL_LOCAL', 'REAL_INTEGRATION', 'LIVE_PROVIDER'):
                errors.append('Unqualified live layer: ' + layer)
            artifacts = record.get('artifacts', [])
            if not artifacts:
                errors.append('Missing raw artifacts: ' + layer)
            for item in artifacts:
                f = (path.parent / item.get('path', '')).resolve()
                if not f.is_relative_to(path.parent.resolve()) or not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != item.get('sha256'):
                    errors.append('Missing, unsafe or changed live artifact: ' + layer)
        if manifest.get('scientific_review') != 'APPROVED':
            errors.append('Scientific review has not been approved')
        if not manifest.get('required_providers') or set(manifest['required_providers']) != set(manifest.get('verified_providers', [])):
            errors.append('Required provider inference matrix is incomplete')
        from .layers import live_regression_errors
        record=manifest.get('live_regression',{})
        raw=(path.parent/record.get('path','')).resolve()
        if (not raw.is_relative_to(path.parent.resolve()) or not raw.is_file()
                or hashlib.sha256(raw.read_bytes()).hexdigest()!=record.get('sha256')):
            errors.append('Hash-bound deferred live-provider regression report is missing')
        else:
            errors.extend(live_regression_errors(json.loads(raw.read_text(encoding='utf-8'))))
        return errors
    except (ValueError, OSError, TypeError, AttributeError):
        return ['Live evidence manifest is malformed']


def main(argv: list[str] | None = None) -> int:
    from .journeys import load_configuration
    uat_defaults=load_configuration(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['quick', 'feature', 'pr', 'full', 'targeted', 'uat', 'release'], default='quick')
    parser.add_argument('--base', default='origin/dev')
    parser.add_argument('--contract', type=Path, action='append')
    parser.add_argument('--target', action='append', default=[], help='unittest module, targeted profile only')
    parser.add_argument('--component', choices=['all', 'backend', 'frontend'], default='all')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--plan', action='store_true', help='Print selection only; returns NOT_RUN (exit 2)')
    parser.add_argument('--live-evidence', type=Path)
    parser.add_argument('--uat-model', default=uat_defaults['model'])
    parser.add_argument('--uat-steps', type=int, default=uat_defaults['max_steps'])
    parser.add_argument('--uat-deadline', type=int, default=uat_defaults['timeout_s'])
    parser.add_argument('--uat-owner-authorization',type=Path,help='Explicit single-use owner exception in external trusted Git metadata; never resets prior failures')
    parser.add_argument('--uat-journey',action='append',help='Declared exploratory journey (currently settings-language only)')
    parser.add_argument('--repair-key', help='Stable PR/task identity, never a head SHA')
    parser.add_argument('--repair-status',action='store_true')
    parser.add_argument('--repair-result', choices=['failure', 'success'], help='Record a completed automatic repair cycle; does not run tests')
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = (args.out or ROOT / 'output/playwright/verification' / stamp).resolve()
    # Avoid writing verification logs or generated data into production sources.
    allowed = (ROOT / 'output/playwright').resolve()
    if not out.is_relative_to(allowed) or out == allowed:
        parser.error('--out must be a run directory inside output/playwright/')
    if out.exists() and any(out.iterdir()):
        parser.error('Run evidence already exists; choose a fresh --out directory')
    out.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.repair_result or args.repair_status:
        if not args.repair_key:
            parser.error('--repair-result requires a stable --repair-key')
        budget = RepairBudget(ROOT / 'agent/repair-ledgers/ledger.json', args.repair_key)
        if args.repair_result == 'failure': budget.record_failure(head)
        elif args.repair_result == 'success': budget.record_success(head)
        print(json.dumps({'attempts': budget.attempts, 'can_repair': budget.can_repair()}))
        return 0 if budget.can_repair() or args.repair_result else 2
    before = identity(ROOT)
    steps, cases, coverage, deferred_tests = [], [], {}, []
    def execute(name: str, command: list[str], cwd: Path = ROOT, timeout: int = 1200) -> dict:
        step = run_command(name, command, cwd, out, timeout); steps.append(step); return step
    try:
        changed = changed_files(ROOT, args.base)
        selection = select(ROOT, changed, args.profile)
    except (subprocess.SubprocessError, OSError) as exc:
        changed, selection = [], {'risk': 'CRITICAL', 'backend_tests': [], 'frontend': False, 'reasons': []}
        steps.append({'id': 'selection', 'status': 'BLOCKED', 'details': 'Cannot establish diff base: ' + str(exc)})
    if args.profile == 'targeted':
        if not args.target or any(not value.replace('.', '').replace('_', '').isalnum() for value in args.target):
            parser.error('targeted requires explicit valid unittest --target names')
        selection.update(backend_tests=args.target, frontend=False)
    if selection.get('blocked_tests'):
        steps.append({'id':'test-inventory','status':'BLOCKED','details':
                      'Unclassified test directories must be registered before execution: '+str(selection['blocked_tests'])})
    contracts = args.contract or sorted((ROOT / 'docs/qa/contracts').glob('*.json'))
    contract_errors = []
    if not contracts:
        contract_errors.append('No feature quality contract was supplied')
    for path in contracts:
        try:
            contract = json.loads(path.read_text(encoding='utf-8'))
            contract_errors.extend(str(path) + ': ' + e for e in validate_contract(contract, ROOT))
            if isinstance(contract, dict): contract_errors.extend(str(path) + ': ' + e for e in validate_tdd(contract, ROOT))
        except (ValueError, OSError, TypeError, AttributeError) as exc: contract_errors.append(str(path) + ': invalid contract (' + type(exc).__name__ + ')')
    from .journeys import browser_plan,relevant_contracts
    contract_data=[json.loads(path.read_text(encoding='utf-8')) for path in contracts] if not contract_errors else []
    browser_selection=browser_plan(ROOT,changed,relevant_contracts(changed,contract_data),args.profile)
    contract_errors.extend(browser_selection['errors'])
    steps.append({'id': 'contract', 'status': 'FAIL' if contract_errors else 'PASS', 'details': contract_errors})
    if args.plan:
        steps.append({'id': 'execution', 'status': 'NOT_RUN'})
    elif args.profile == 'uat' and not contract_errors:
        budget=RepairBudget(ROOT/'agent/repair-ledgers/ledger.json',args.repair_key or 'TASK-UAT-LOCAL-ADAPTER')
        if any(j!='settings-language' for j in args.uat_journey or ['settings-language']):
            steps.append({'id':'uat-exploration','status':'BLOCKED','details':'Requested exploratory journey adapter is NOT_IMPLEMENTED; no model was called'})
        elif not budget.can_repair() and not args.uat_owner_authorization:
            steps.append({'id':'uat-exploration','status':'BLOCKED','details':'Three failed repair cycles exhausted; preserve evidence and stop this loop'})
        else:
            npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm') or 'npm'
            build=execute('uat-current-frontend-build',[npm,'run','build'],ROOT/'frontend')
            if build['status']!='PASS':
                steps.append({'id':'uat-exploration','status':'BLOCKED','details':'Build current frontend before exploratory acceptance; no model was called'})
            else:
                from .uat import execute as explore
                folder=out/'uat';folder.mkdir(exist_ok=False)
                authorized=False
                try:
                    if args.uat_owner_authorization:
                        adapter=ROOT/'output/playwright/browser-uat-env'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
                        if not adapter.is_file():raise ValueError('Prepare the verified optional Browser Use environment before consuming the one owner execution')
                        from .uat_authorization import consume
                        permission=consume(ROOT,args.uat_owner_authorization,before['sha256'],head,args.uat_model,args.uat_steps,args.uat_deadline)
                        authorized=True
                        (folder/'owner-authorization-receipt.json').write_text(json.dumps(permission,indent=2)+'\n',encoding='utf-8')
                    uat=explore(folder,model=args.uat_model,steps=args.uat_steps,deadline=args.uat_deadline,source=before['sha256'],owner_limit=authorized)
                except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
                    uat={'decision':'BLOCKED','scope':'Exploratory startup did not complete',
                         'error':type(exc).__name__+': '+str(exc)[:1000]}
                    (folder/'uat-report.json').write_text(json.dumps(uat,indent=2)+'\n',encoding='utf-8')
                if authorized:
                    from .uat_authorization import finish
                    finish(ROOT,uat['decision'])
                steps.append({'id':'uat-exploration','status':uat['decision'] if uat['decision'] in ('PASS','FAIL') else 'BLOCKED',
                              'details':uat.get('error') or uat.get('reason') or uat['scope']})
        cases.append({'id':'uat.first-time.settings-language','status':steps[-1]['status'],'details':steps[-1]['details']})
    elif not contract_errors and not any(s['status'] == 'BLOCKED' for s in steps):
        execute('protected-files', [sys.executable, 'tools/protect_agent_resources.py', '--base', args.base])
        if args.component == 'all' and args.profile in ('feature', 'pr', 'full', 'release'):
            execute('test-discovery',[sys.executable,'scripts/discover_tests.py','--out',str(out/'test-inventory.json')])
            execute('workflow-contract-policy', [sys.executable, 'scripts/quality_gate.py', 'policy'])
            execute('workflow-syntax', [sys.executable, 'scripts/check_workflows.py'], timeout=90)
            node = shutil.which('node.exe' if os.name == 'nt' else 'node') or 'node'
            policy_tests = sorted(str(path) for path in (ROOT/'.github/scripts').glob('*.test.cjs'))
            if policy_tests:
                execute('github-policy-tests', [node, '--test', *policy_tests], timeout=60)
            else:
                steps.append({'id':'github-policy-tests','status':'BLOCKED','details':'Explicit policy test files are missing; never invoke unbounded Node discovery'})
        python_files = [p for p in changed if p.endswith('.py') and (ROOT/p).is_file()]
        if python_files:
            execute('syntax-lint', [sys.executable, '-m', 'ruff', 'check', '--target-version', 'py311', '--select', 'E9,F63,F7,F82', *python_files])
        if args.component != 'frontend' and selection['backend_tests']:
            if args.profile in ('pr', 'full', 'release'):
                execute('backend', [sys.executable, 'tools/backend_quality_gate.py', '--profile', 'full',
                        '--layer', 'all' if args.profile in ('full','release') else 'software',
                        '--i-understand-full-suite', '--require-complete', '--output-dir', str(out/'backend')])
                report_path = out/'backend/report.json'
                if report_path.is_file():
                    backend_report=json.loads(report_path.read_text(encoding='utf-8'))
                    cases.extend(backend_report.get('cases', []))
                    coverage['backend']=backend_report.get('coverage',{})
                    deferred_tests.extend(backend_report.get('deferred_tests',[]))
            else:
                execute('backend', [sys.executable, '-m', 'devtools.verification.unittest_worker', str(out/'unittest.json'), *selection['backend_tests']])
                if (out/'unittest.json').is_file():
                    unit=json.loads((out/'unittest.json').read_text(encoding='utf-8'))
                    cases.extend(unit.get('cases', []));deferred_tests.extend(unit.get('deferred_tests',[]))
        if args.component != 'backend' and selection['frontend']:
            npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm') or 'npm'
            if not (ROOT/'frontend/node_modules').is_dir():
                steps.append({'id': 'frontend-dependencies', 'status': 'BLOCKED', 'details': 'Run npm ci in frontend before verification'})
            else:
                execute('frontend-types', [npm, 'run', 'typecheck'], ROOT/'frontend')
                command = [npm, 'run', 'test:coverage', '--', '--maxWorkers=2', '--reporter=json', '--outputFile='+str(out/'frontend-tests.json')]
                execute('frontend-tests', command, ROOT/'frontend')
                if (out/'frontend-tests.json').is_file():
                    for suite in json.loads((out/'frontend-tests.json').read_text(encoding='utf-8')).get('testResults', []):
                        for test in suite.get('assertionResults', []):
                            cases.append({'id': test.get('fullName'), 'status': {'passed':'PASS','failed':'FAIL'}.get(test.get('status'),'NOT_RUN'), 'details':'\n'.join(test.get('failureMessages',[]))})
                cov = ROOT/'frontend/coverage/coverage-summary.json'
                if cov.is_file():
                    shutil.copy2(cov, out/'frontend-coverage.json')
                    coverage['frontend']=json.loads(cov.read_text(encoding='utf-8')).get('total',{})
                if args.profile != 'quick': execute('frontend-build', [npm, 'run', 'build'], ROOT/'frontend')
                if args.profile == 'feature' or (args.profile in ('pr','full','release') and args.component=='all'):
                    browser_command=[sys.executable,'-m','devtools.verification.browser',
                                     '--profile',args.profile,'--base',args.base,'--out',str(out/'browser')]
                    if args.profile in ('feature','pr'): browser_command.append('--offline-all')
                    execute('deterministic-browser', browser_command, timeout=1900 if args.profile in ('full','release') else 700)
                    boundaries=out/'browser/boundaries.json'
                    if boundaries.is_file():
                        cases.extend({**case,'mode':'REAL_LOCAL'} for case in json.loads(boundaries.read_text(encoding='utf-8')).get('cases',[]))
                    browser_results=out/'browser/results.json'
                    if browser_results.is_file():
                        def browser_cases(suites):
                            for suite in suites:
                                yield from browser_cases(suite.get('suites',[]))
                                for spec in suite.get('specs',[]):
                                    for test in spec.get('tests',[]):
                                        results=test.get('results',[])
                                        passed=results and all(r.get('status')=='passed' for r in results)
                                        status='PASS' if passed else 'SKIP' if results and all(r.get('status')=='skipped' for r in results) else 'FAIL' if results else 'NOT_RUN'
                                        yield {'id':'playwright.'+spec.get('title','unknown'),
                                               'status':status,
                                               'mode':'REAL_LOCAL','details':str([r.get('errors',[]) for r in results]) if not passed else None,
                                               'scope':'Actual browser; controlled fault cases identify fixtures in their attachments'}
                        cases.extend(browser_cases(json.loads(browser_results.read_text(encoding='utf-8')).get('suites',[])))
        if args.profile in ('full','release'):
            errors = validate_live(args.live_evidence, before['sha256'], head)
            steps.append({'id':'live-qualification', 'status':'BLOCKED' if errors else 'PASS', 'details':errors})
        if args.profile == 'release':
            from .promotion import home,policy_errors
            try:
                owner_policy=json.loads((home(ROOT)/'policy.json').read_text(encoding='utf-8'))
                errors=policy_errors(ROOT,owner_policy)
            except (OSError,ValueError,TypeError,AttributeError):
                errors=['Explicit trusted owner policy for native main promotion is not registered']
            steps.append({'id':'owner-release-policy','status':'BLOCKED' if errors else 'PASS',
                          'details':errors or ['Owner-authorized automatic native promotion; GitHub required checks and provenance remain mandatory']})
    after = identity(ROOT)
    if before != after: steps.append({'id':'stable-source','status':'BLOCKED','details':'Source inputs changed during verification; rerun against a stable checkout'})
    if any(c.get('status') == 'NOT_RUN' for c in cases):
        steps.append({'id':'executed-cases','status':'BLOCKED','details':'Selected cases were not executed'})
    if args.profile in ('pr','full','release') and any(c.get('status') == 'SKIP' for c in cases):
        steps.append({'id':'mandatory-cases','status':'BLOCKED','details':'Skipped cases cannot qualify a mandatory gate'})
    states = {s['id']:s['status'] for s in steps}
    decision = aggregate(states, list(states))
    if args.plan: decision = 'NOT_RUN'
    groups = fingerprints(cases)
    report = {'schema_version':1, 'decision':decision, 'profile':args.profile, 'component':args.component,
              'mode':'REAL_LOCAL' if args.profile=='uat' else 'MIXED' if any(c.get('mode')=='REAL_LOCAL' for c in cases) else 'MOCKED', 'head_sha':head, 'base':args.base, 'timestamp':stamp,
              'source':before, 'source_stable':before==after, 'environment':{'python':sys.version,'platform':platform.platform()},
              'changed':changed, 'selection':selection, 'browser_selection':browser_selection, 'steps':steps,
              'separate_live_inventory':{'status':'NOT_RUN','tests':selection.get('separate_live_tests',[]),
                                         'reason':'Legacy external/model tests require separate explicit authorization, model selection and isolated live execution; offline selection never starts them'},
              'counts':{state:sum(c.get('status')==state for c in cases) for state in ('PASS','FAIL','ERROR','SKIP','NOT_RUN','BLOCKED','UNVERIFIED')},
              'cases':cases, 'coverage':coverage, 'coverage_policy':{'mode':'INFORMATIONAL','percentage_gate':False}, 'root_failures':groups,
              'deferred_tests':deferred_tests,
              'limitations':['Quick/feature/targeted are scoped development checks, not release acceptance',
                            'No cached passing result is reused. Incremental selection saves work, never replaces PR/full gates',
                            'Live layers require separately executed, matching-source evidence; unavailable layers block full',
                            'No token savings percentage has been measured']}
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines = ['VERIFY: '+decision, 'Profile: '+args.profile+' / '+args.component,
             'Tests: '+json.dumps(report['counts']), 'Affected: '+str(len(changed))+' files; risk '+selection['risk']]
    lines += ['Root cause: '+g['cause'][:220]+' ('+str(g['count'])+' cases)' for g in groups[:5]]
    lines += ['Gate: '+s['id']+' '+s['status']+' '+str(s.get('details') or '')[:240] for s in steps if s['status']!='PASS'][:8]
    lines += ['Evidence: '+str(out/'report.json'), 'Next action: '+('Read the first relevant raw log; repair at most three cycles' if decision!='PASS' else 'Use independent CI before merge; full qualification before promotion')]
    (out/'summary.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8'); print('\n'.join(lines))
    if args.profile=='pr' and args.component=='all':
        from .branch_policy import record_report
        record_report(ROOT,out/'report.json',report)
    return 0 if decision == 'PASS' else 2 if decision in ('BLOCKED','NOT_RUN') else 1
