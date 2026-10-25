"""Repository-native QA inventory, seeded graph cases and fail-closed evidence gates.

Inventory/generation never claims a workflow executed. All commands use disposable
storage, and report raw coverage counts rather than redefining production scope.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import random
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    mode: Literal['UNIT', 'INTEGRATION', 'LIVE_PROVIDER', 'REAL_E2E', 'SCIENTIFIC', 'SIMULATION']
    status: Literal['PASSED', 'FAILED', 'ERROR', 'BLOCKED', 'SKIPPED', 'UNAVAILABLE', 'UNSUPPORTED', 'UNVERIFIED']
    executed: bool
    mock_used: bool = False
    source_revision: str
    command: list[str]
    artifacts: list[str]
    scientific_verified: bool = False
    replay_executed: bool = False
    actual_provider: str | None = None
    requested_provider: str | None = None
    fallback_reason: str | None = None

    @model_validator(mode='after')
    def trustworthy(self):
        if self.status == 'PASSED' and (not self.executed or not self.command or not self.source_revision):
            raise ValueError('PASSED requires executed assertions, source and command')
        if self.mode in ('LIVE_PROVIDER', 'REAL_E2E', 'SCIENTIFIC'):
            if self.mock_used:
                raise ValueError('Mock execution is invalid as live/scientific evidence')
            if self.status == 'PASSED' and not self.artifacts:
                raise ValueError('Live/scientific PASS requires execution artifacts')
        if self.mode in ('LIVE_PROVIDER', 'REAL_E2E') and self.status == 'PASSED' and not self.actual_provider:
            raise ValueError('Actual executing provider is required')
        if self.scientific_verified and (self.mode != 'SCIENTIFIC' or not self.replay_executed or not self.artifacts or self.status != 'PASSED'):
            raise ValueError('Scientific verification requires independently replayed evidence')
        if (self.actual_provider and self.requested_provider and self.actual_provider != self.requested_provider
                and not self.fallback_reason):
            raise ValueError('Provider fallback must preserve provenance')
        for artifact in self.artifacts:
            target = Path(artifact)
            if target.is_absolute() or '..' in target.parts:
                raise ValueError('Evidence paths must be relative to the run directory')
        return self


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in ('backend', 'frontend/src', 'tools') for p in (ROOT / directory).rglob('*')
            if p.is_file() and p.suffix in ('.py', '.ts', '.tsx', '.mjs')}


def audit_source(text: str, path: str) -> list[dict]:
    """Focused AST rules for confirmed historical fake-success mechanisms."""
    tree = ast.parse(text)
    findings = []
    science_keys = {'confidence', 'tokens', 'citations_checked', 'papers_indexed', 'evidence_links',
                    'files_generated', 'bytes_processed', 'psnr_db', 'ssim', 'accuracy', 'pass_at_1',
                    'rubric_score', 'tests_passed', 'coverage_pct', 'reproducibility_score'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and path.endswith(('harness.py', 'workflow_runtime.py')):
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value in science_keys
                        and isinstance(value, ast.Constant) and isinstance(value.value, (int, float))):
                    findings.append({'rule': 'QA001', 'path': path, 'line': value.lineno,
                                     'message': f'Hardcoded scientific/execution metric: {key.value}'})
        if (isinstance(node, ast.Assign) and path.endswith('reproducibility.py')
                and any('replayed_metrics' in ast.unparse(target) for target in node.targets)
                and ('expected' in ast.unparse(node.value) or ast.unparse(node.value) in ('val', 'v'))):
            findings.append({'rule': 'QA002', 'path': path, 'line': node.lineno,
                             'message': 'Expected metrics copied into replay measurements'})
        if isinstance(node, (ast.Import, ast.ImportFrom)) and '/live_e2e/' in path:
            names = [n.name for n in node.names]
            if (getattr(node, 'module', '') or '').startswith('unittest.mock') or any(n.startswith('unittest.mock') for n in names):
                findings.append({'rule': 'QA003', 'path': path, 'line': node.lineno,
                                 'message': 'Mock import in live-provider test module requires separation'})
    return findings


def audit():
    files = [*list((ROOT / 'backend').rglob('*.py')), *list((ROOT / 'tests/live_e2e').glob('*.py'))]
    findings = [f for path in files for f in audit_source(path.read_text('utf-8'), path.relative_to(ROOT).as_posix())]
    return {'inspected_locations': len(files), 'findings': findings, 'passed': not findings}


def generated_graphs(seed: int, count: int):
    rng = random.Random(seed)
    for case in range(count):
        length = rng.randint(2, 10)
        nodes = [{'id': f'n{i}', 'type': 'start' if i == 0 else 'end' if i == length - 1 else 'condition',
                  'data': {'config': {'condition_rule': 'pass_count >= 0'}}} for i in range(length)]
        edges = [{'id': f'e{i}', 'source': f'n{i}', 'target': f'n{i+1}'} for i in range(length - 1)]
        valid = {'id': f'seed-{seed}-case-{case}', 'nodes': nodes, 'edges': edges}
        yield {'seed': seed, 'expected_valid': True, 'graph': valid}
        invalid = json.loads(json.dumps(valid))
        invalid['edges'].append({'id': 'dangling', 'source': nodes[-1]['id'], 'target': 'missing-node'})
        yield {'seed': seed, 'expected_valid': False, 'graph': invalid}


def inventory():
    from backend.app import app
    from backend.core.config import PROVIDERS
    from backend.execution.harness import list_workflows
    from backend.execution.workflow_nodes import NODE_REGISTRY, validate_workflow_graph
    from backend.execution.workflow_templates import list_templates
    from backend.research_engines.registry import FACTORIES
    workflows = list_templates() + list_workflows()
    records = []
    for workflow in workflows:
        raw = json.dumps(workflow, sort_keys=True, ensure_ascii=False).encode()
        records.append({'id': workflow.get('id'), 'sha256': hashlib.sha256(raw).hexdigest(),
                        'nodes': [{'id': n.get('id'), 'type': n.get('type') or n.get('data', {}).get('node_type'),
                                   'config': n.get('data', {}).get('config', n.get('data', {}).get('params', {}))}
                                  for n in workflow.get('nodes', [])],
                        'edges': workflow.get('edges', []), 'validation': validate_workflow_graph(workflow),
                        'execution_status': 'UNVERIFIED', 'execution_level': workflow.get('execution_level', 'unspecified')})
    operations = [{'method': method.upper(), 'path': path, 'operation_id': spec.get('operationId'), 'status': 'UNVERIFIED'}
                  for path, methods in app.openapi()['paths'].items() for method, spec in methods.items()]
    return {'scope': 'registered templates and disposable-profile workflows; private user workflows are not copied',
            'workflows': records, 'node_types': sorted(NODE_REGISTRY), 'cloud_providers': sorted(PROVIDERS),
            'research_engines': sorted(FACTORIES), 'api_operations': operations,
            'source_files': source_hashes(), 'ui_routes_and_controls': 'Browser attachments required; no static completeness claim'}


def release_decision(backend: dict, frontend: dict, evidence: list[dict]):
    """Return a verdict only for the measured scope; absent mandatory layers block."""
    reasons = []
    if not backend or not frontend or not evidence:
        reasons.append('Missing mandatory backend, frontend or live evidence')
    summary = backend.get('summary', {})
    if not summary.get('total_run') or any(summary.get(k, 0) for k in ('failures', 'errors', 'skipped')):
        reasons.append('Backend cases missing, failing, erroneous or skipped')
    cov = backend.get('coverage', {})
    for covered, total in [('covered_lines', 'num_statements'), ('covered_branches', 'num_branches')]:
        if not cov.get(total) or cov.get(covered) != cov.get(total):
            reasons.append(f'Backend {covered}/{total} is below 100%')
    for metric in ('lines', 'statements', 'branches', 'functions'):
        measured = frontend.get('total', {}).get(metric, {})
        if not measured.get('total') or measured.get('covered') != measured.get('total'):
            reasons.append(f'Frontend {metric} is below 100%')
    records = [EvidenceRecord.model_validate(item) for item in evidence]
    for mode in ('REAL_E2E', 'LIVE_PROVIDER', 'SCIENTIFIC'):
        if not any(r.mode == mode and r.status == 'PASSED' for r in records):
            reasons.append(f'Missing passing {mode} evidence')
    if any(r.status != 'PASSED' for r in records):
        reasons.append('Mandatory evidence includes non-passing results')
    return {'decision': 'NO-GO' if reasons else 'CONDITIONAL', 'reasons': reasons,
            'limitations': ['Provider/platform/manual and scientific review qualification must also be satisfied']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inventory', 'generate', 'audit', 'release'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261024)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--backend', type=Path)
    parser.add_argument('--frontend', type=Path)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='phdlab-qa-inventory-') as data:
        os.environ['PHDLAB_DATA_DIR'] = data
        if args.command == 'inventory':
            report = inventory()
        elif args.command == 'generate':
            from backend.execution.workflow_nodes import validate_workflow_graph
            cases = list(generated_graphs(args.seed, args.count))
            for case in cases:
                case['actual'] = validate_workflow_graph(case['graph'])
                case['passed'] = case['actual']['valid'] == case['expected_valid']
            report = {'mode': 'SCHEMA_CONTRACT', 'seed': args.seed, 'cases': cases,
                      'passed': all(c['passed'] for c in cases), 'limitations': ['Not research or provider execution coverage']}
        elif args.command == 'audit':
            report = audit()
        else:
            def read(path):
                return json.loads(path.read_text('utf-8')) if path and path.is_file() else {}
            report = release_decision(read(args.backend), read(args.frontend), read(args.evidence) or [])
    report['at'] = datetime.now(UTC).isoformat()
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), 'utf-8')
    print(json.dumps({'command': args.command, 'out': str(args.out), 'passed': report.get('passed'), 'decision': report.get('decision')}))
    return 0 if report.get('passed', True) and report.get('decision') != 'NO-GO' else 1


if __name__ == '__main__':
    raise SystemExit(main())
