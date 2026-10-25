"""Publish measured local QA evidence without promoting missing checks to success."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path):
    return json.loads(path.read_text('utf-8-sig'))


def write(path: Path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content, indent=2, ensure_ascii=False) + '\n', 'utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run, out = args.run.resolve(), args.out.resolve()
    if not run.is_relative_to(ROOT / 'output/playwright') or not out.is_relative_to(ROOT / 'docs/qa/evidence'):
        parser.error('Use an isolated output/playwright run and docs/qa/evidence publication directory')
    backend = read(run / 'backend-final/report.json')
    frontend = read(run / 'frontend-qualified-serial.json')
    coverage = read(run / 'frontend-coverage-summary.json')
    golden = read(run / 'golden-verified/report.json')
    providers = read(run / 'providers-cli/report.json')
    benchmark = read(run / 'native-vs-wrapped-serial/report.json')
    inventory = read(run / 'inventory-final.json')
    cases = []
    attempts = []
    for name in ('backend-release', 'backend-current', 'backend-qualified', 'backend-final'):
        path = run / name / 'report.json'
        if path.is_file():
            report = read(path)
            attempts.append({'run': name, 'mode': 'UNIT_OFFLINE', 'summary': report['summary'],
                             'source_stable': report['metadata'].get('source_stable')})
            cases.extend({'attempt': name, 'mode': 'UNIT_OFFLINE', **c} for c in report['cases'])
    for name in ('baseline-frontend', 'frontend-current', 'frontend-final', 'frontend-release',
                 'frontend-qualified', 'frontend-qualified-serial'):
        path = run / (name + '.json')
        if path.is_file():
            report = read(path)
            attempts.append({'run': name, 'mode': 'UNIT_JS_DOM', 'total': report['numTotalTests'],
                             'passed': report['numPassedTests'], 'failed': report['numFailedTests'],
                             'pending': report['numPendingTests']})
            for suite in report['testResults']:
                for case in suite['assertionResults']:
                    cases.append({'attempt': name, 'mode': 'UNIT_JS_DOM', 'id': case['fullName'],
                                  'status': case['status'], 'duration': case.get('duration'),
                                  'details': '\n'.join(case.get('failureMessages', []))})
    browser_summary = {}
    for name in ('browser-2d', 'browser-2d-release', 'browser-2d-final', 'browser-3d', 'browser-3d-final'):
        path = run / name / 'results.json'
        if not path.is_file():
            continue
        report = read(path)
        attempts.append({'run': name, 'mode': 'REAL_E2E', 'stats': report['stats']})
        browser_summary[name] = report['stats']

        def walk(suites, prefix='', attempt=name):
            for suite in suites:
                label = prefix + suite.get('title', '') + ' / '
                for spec in suite.get('specs', []):
                    for test in spec.get('tests', []):
                        for result in test.get('results', []):
                            cases.append({'attempt': attempt, 'mode': 'REAL_E2E', 'id': label + spec['title'],
                                          'status': result['status'], 'duration': result.get('duration'),
                                          'details': result.get('error', {}).get('message', '')})
                walk(suite.get('suites', []), label)
        walk(report.get('suites', []))
    for name in ('golden-first', 'golden-second', 'golden-third', 'golden-final', 'golden-verified'):
        path = run / name / 'report.json'
        if path.is_file():
            report = read(path)
            invalidated = name in {'golden-third', 'golden-final'}
            attempts.append({'run': name, 'mode': 'EXECUTED_SYNTHETIC_EXPERIMENT',
                             'script_status': report['status'],
                             'acceptance': 'INVALIDATED_BY_VISUAL_QA' if invalidated else report['status']})
            cases.extend({'attempt': name, 'mode': 'EXECUTED_SYNTHETIC_EXPERIMENT', 'id': c['id'],
                          'status': 'UNVERIFIED_LEGACY_EXPORT' if invalidated and c['id'] in
                          {'figure-store-render', 'paper-writer-and-latex-export', 'native-paper-pdf-compilation'} else c['status'],
                          'duration': c.get('elapsed_s'), 'details': c.get('error', '')} for c in report['cases'])
    for name in ('native-vs-wrapped', 'native-vs-wrapped-serial'):
        report = read(run / name / 'report.json')
        attempts.append({'run': name, 'mode': 'LIVE_PROVIDER', 'status': report['status'], 'summary': report['summary']})
        for i, row in enumerate(report['rows']):
            cases.append({'attempt': name, 'mode': 'LIVE_PROVIDER', 'id': str(row.get('id', i)),
                          'status': 'PASSED' if row.get('passed') else 'FAILED',
                          'duration': row.get('elapsed_s'), 'details': json.dumps(row, ensure_ascii=False)})
    out.mkdir(parents=True, exist_ok=True)
    for relative in ('backend-final/report.json', 'frontend-coverage-summary.json', 'api-task-parity.json',
                     'api-parity.json', 'static-integrity-final.json', 'cli-live/report.json',
                     'mcp-probe/report.json', 'providers-cli/report.json', 'native-vs-wrapped/report.json',
                     'native-vs-wrapped-serial/report.json', 'golden-verified/report.json',
                     'golden-verified/paper.pdf', 'golden-verified/paper.md', 'golden-verified/main.tex',
                     'golden-verified/references.bib', 'golden-verified/figure.png',
                     'golden-verified/experiment/raw.csv', 'golden-verified/experiment/metrics.json',
                     'golden-verified/replay/raw.csv', 'golden-verified/replay/metrics.json'):
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run / relative, destination)
    write(out / 'attempts.json', attempts)
    write(out / 'inventory-summary.json', {k: inventory[k] for k in
          ('scope', 'node_types', 'cloud_providers', 'research_engines', 'api_operations')})
    with (out / 'all-case-results.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['attempt', 'mode', 'id', 'status', 'duration', 'details'], extrasaction='ignore')
        writer.writeheader()
        writer.writerows(cases)
    with (out / 'workflow-inventory.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['id', 'node_count', 'edge_count', 'schema_valid', 'execution_status', 'sha256'])
        writer.writerows((w['id'], len(w['nodes']), len(w['edges']), w['validation']['valid'],
                          w['execution_status'], w['sha256']) for w in inventory['workflows'])
    summary = {
        'at': datetime.now(UTC).isoformat(), 'run_root': run.relative_to(ROOT).as_posix(),
        'release_decision': 'NO-GO', 'backend': backend['summary'], 'backend_coverage': backend['coverage'],
        'backend_source_stable': backend['metadata']['source_stable'],
        'frontend': {k: frontend[k] for k in ('numTotalTests', 'numPassedTests', 'numFailedTests', 'numPendingTests')},
        'frontend_coverage': coverage['total'], 'browser': browser_summary,
        'cli': read(run / 'cli-live/report.json'), 'mcp': read(run / 'mcp-probe/report.json'),
        'providers': [{'provider': p['provider'], 'passed': p['passed'], 'elapsed_s': p['elapsed_s'],
                       'state': p['health_after']['state']} for p in providers],
        'benchmark': benchmark['summary'], 'golden_cases': len(golden['cases']),
        'scientific_verified': False,
        'blockers': ['Mandatory backend skips remain',
                     'Cloud credentials absent, Gemini auth absent, Claude quota exhausted, Ollama unavailable',
                     'Every workflow/provider/viewport/control is not yet live-qualified',
                     'Full context/memory/router/policy consolidation remains incomplete',
                     'Remote CI and independent scientific review not qualified'],
    }
    write(out / 'summary.json', summary)
    b, c, f = backend['summary'], backend['coverage'], coverage['total']
    table = f"""| Layer | Executed result | Scope |
|---|---|---|
| Backend | {b['passed']}/{b['total_run']} pass; {b['failures']} failures, {b['errors']} errors, {b['skipped']} skips | Offline unit/integration; stable source hash: {backend['metadata']['source_stable']} |
| Backend lines | {c['covered_lines']}/{c['num_statements']} ({100*c['covered_lines']/c['num_statements']:.2f}%) | All backend production sources in .coveragerc |
| Backend branches | {c['covered_branches']}/{c['num_branches']} ({100*c['covered_branches']/c['num_branches']:.2f}%) | Combined coverage.py figure: {c['percent_covered']}%, not line coverage |
| Frontend | {frontend['numPassedTests']}/{frontend['numTotalTests']} pass; {frontend['numPendingTests']} skips | Vitest/jsdom, 2 workers |
| Frontend coverage | Lines {f['lines']['pct']}%; branches {f['branches']['pct']}%; functions {f['functions']['pct']}%; statements {f['statements']['pct']}% | Whole production TS/TSX, including unimported files |
| 2D | {browser_summary['browser-2d-final']['expected']} passed, {browser_summary['browser-2d-final']['unexpected']} failed | Chromium, real HTTP/state/LM; selected journeys |
| 3D | {browser_summary['browser-3d-final']['expected']} passed, {browser_summary['browser-3d-final']['unexpected']} failed | WebGL2, camera pixels, lighting, dock, return to 2D |
| CLI | {summary['cli']['status']} | Real child process, 8 settings groups, EN/VI persistence, actual 391 response |
| Golden Thread | {len(golden['cases'])} steps {golden['status']} | Actual CPU synthetic experiment, replay, recomputation, real figure and compiled paper |
| Native vs wrapped | Native {benchmark['summary']['native']['passed']}/6; wrapped {benchmark['summary']['wrapped']['passed']}/6 | Spark 4B, three tasks repeated twice; earlier two model-unloaded errors retained |
"""
    evidence_link = 'evidence/' + out.name
    write(ROOT / 'docs/qa/RELEASE_READINESS.md', f"""# Full harness release assessment — 2026-10-25

**NO-GO. The requested 100% mandatory regression and all-provider qualification have not been achieved.**
The passing cases below certify only their assertions. Missing providers, skipped cases and unsupported benchmark executors are not successes.

{table}

Canonical machine report: [{evidence_link}/summary.json]({evidence_link}/summary.json).
All recorded attempt/case outcomes: [attempts]({evidence_link}/attempts.json), [CSV]({evidence_link}/all-case-results.csv).
Raw traces, screenshots, request logs and console output remain in `{run.relative_to(ROOT).as_posix()}`; they are intentionally ignored by Git.

## Failures retained and repaired

- Frontend baseline: 173/174; native-launch accessible label fixed. A later unconstrained-worker run had two async timeouts; the bounded 2-worker run passed all 174. No assertion was removed to hide these failures.
- Backend historical failures exposed completion/cancellation races, stale gateway reconciliation and nondeterministic temporal retrieval. Stored timestamps now define temporal order; equal instants use record ID. See each attempt and exact test details in the CSV.
- 2D multi-turn chat returned 84 rather than 782 after unrelated chat context poisoned the turn. Default context no longer imports unrelated conversations; selected/folder-shared sources remain supported. Final 2D suite passed.
- Initial 3D selector was ambiguous; exact control selection fixed the test. Final WebGL2 test and screenshot inspection passed the measured behavior.
- First Golden Thread attempts failed on code-project prerequisites. Two subsequent script passes were **invalidated by visual QA**: PNG exports were fixed placeholder grids. The renderer now derives vector PDF and raster PNG from the same SVG; legacy PNG/PDF versions require regeneration. Only `golden-verified/paper.pdf` is accepted in this evidence pack.
- The first native/wrapped benchmark had two model-unloaded errors. The serial rerun passed 12/12 calls. Their cause is not established; this sample does not prove sustained provider reliability.

## Remaining work

Backend coverage has {c['num_statements']-c['covered_lines']} uncovered executable lines and {c['num_branches']-c['covered_branches']} uncovered branches. Frontend has {f['lines']['total']-f['lines']['covered']} uncovered lines and {f['branches']['total']-f['branches']['covered']} uncovered branches. Add behavior oracles without reducing denominators, mocking live runs, changing assertions to success, or misreporting required regression success. Coverage is informational under the current owner policy.

Complete native application window checks, full EN/VI labeling, all registered workflow execution adapters, every required viewport/control, full architectural consolidation, remaining providers, remote Windows/Linux CI, and independent scientific review. Auth/quota/services require actual external availability; subscription CLI access does not imply cloud API credentials.

The CPU experiment is an explicitly synthetic QA fixture. Its paper is a reproducibility artifact, not a claim of new research or publication readiness.
""")
    write(out / 'manifest.json', {'algorithm': 'sha256', 'files': {
        p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'manifest.json'}})
    print(json.dumps({'decision': 'NO-GO', 'out': str(out), 'case_records': len(cases)}))


if __name__ == '__main__':
    main()
