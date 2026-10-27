"""Deterministic feature/persona selection, with no browser or model side effects."""
from __future__ import annotations
import fnmatch
import json
from pathlib import Path
from .uat_gate import requirements


def load_configuration(root: Path) -> dict:
    config = json.loads((root / 'devtools/verification/uat_config.json').read_text(encoding='utf-8'))
    if config.get('schema_version') != 1 or len(config.get('personas', {})) != 5:
        raise ValueError('Invalid versioned UAT persona configuration')
    return config


def relevant_contracts(changed: list[str], contracts: list[dict]) -> list[dict]:
    """Unchanged contracts still apply when their declared modules are edited."""
    return [c for c in contracts if isinstance(c, dict) and
            any(fnmatch.fnmatchcase(path, pattern) for path in changed
                for pattern in c.get('affected_modules', []) if isinstance(pattern, str))]


def browser_plan(root: Path, changed: list[str], contracts: list[dict], profile: str, all_offline: bool = False) -> dict:
    config = load_configuration(root)
    policy = requirements(changed, contracts)
    journeys = config['journeys']
    selected = set(policy['journeys'])
    selected.update(name for name, record in journeys.items()
                    if any(fnmatch.fnmatchcase(p, pattern) for p in changed for pattern in record['paths']))
    if profile in ('full', 'release'):
        selected.update(journeys)
    if all_offline:
        selected.update(name for name,record in journeys.items() if not record['needs_model'])
    tests = list(config['smoke'])
    errors, states = [], {}
    # Routine CI discovers new software suites automatically. Existing opt-in
    # inference suites retain their explicit classification and are not started.
    model_tests={test for record in journeys.values() if record['needs_model'] for test in record['tests']}
    software_tests=set(config['smoke']) | {test for record in journeys.values() if not record['needs_model'] for test in record['tests']}
    inventory=[]
    directory=(root/'frontend/e2e').resolve()
    for path in sorted(directory.rglob('*.spec.ts')):
        if not path.resolve().is_relative_to(directory):
            errors.append('Playwright suite escapes repository: '+path.name);continue
        name=path.relative_to(directory).as_posix();inventory.append(name)
        if (all_offline or profile in ('full','release')) and (name not in model_tests or name in software_tests or profile in ('full','release')):
            if name not in tests:tests.append(name)
    for name in sorted(selected):
        record = journeys.get(name)
        if record is None:
            states[name] = 'NOT_IMPLEMENTED'; errors.append('Unknown contract journey: ' + name); continue
        states[name] = 'NOT_RUN' if record['adapter'] != 'NOT_IMPLEMENTED' else 'NOT_IMPLEMENTED'
        # Routine CI never silently spends inference quota or launches native providers.
        if record['needs_model'] and profile not in ('full', 'release'):
            continue
        for test in record['tests']:
            if not (root / 'frontend/e2e' / test).is_file():
                errors.append('Missing executable Playwright suite: ' + test)
            elif test not in tests:
                tests.append(test)
    # Preserve the owner's required 2D -> 3D order. Native CLI is a separate live layer.
    tests.sort(key=lambda name: name == 'office3d.spec.ts')
    return {'schema_version': 1, 'tests': tests, 'discovered_tests':inventory,
            'deferred_model_tests':sorted(set(inventory)&model_tests-set(tests)), 'journeys': states, 'exploration': policy,
            'errors': errors, 'calls_model': False, 'status': 'NOT_RUN',
            'scope': 'Selection only; deterministic execution and exploratory qualification are separate',
            'selection_mode': 'ALL_NON_MODEL' if all_offline else 'DIFF_OR_PROFILE',
            'personas': {name: [j for j in ids if j in selected] for name, ids in config['personas'].items()}}


def execution_groups(tests: list[str]) -> list[tuple[str,list[str]]]:
    """Playwright sorts files internally; separate invocations enforce actual 2D -> 3D."""
    def three(name):return name=='office3d.spec.ts' or '.3d.' in name or name.startswith('3d/')
    return [(phase,items) for phase,items in [('2d',[n for n in tests if not three(n)]),
                                              ('3d',[n for n in tests if three(n)])] if items]
