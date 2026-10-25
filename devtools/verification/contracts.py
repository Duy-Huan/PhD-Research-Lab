"""Machine-checked feature contracts; prose alone cannot satisfy traceability."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MODES = {'MOCKED', 'REAL_LOCAL', 'REAL_INTEGRATION', 'LIVE_PROVIDER'}


def validate_contract(contract: dict, root: Path) -> list[str]:
    if not isinstance(contract, dict):
        return ['Contract must be an object']
    errors = []
    required = ['id', 'title', 'risk', 'mode', 'user_story', 'requirements', 'nonfunctional',
                'inputs', 'outputs', 'preconditions', 'postconditions', 'dependencies',
                'affected_modules', 'acceptance_criteria', 'scenarios', 'recovery',
                'test_environment', 'skill_sources', 'review']
    for key in required:
        if not contract.get(key):
            errors.append('Missing contract field: ' + key)
    for key in ('requirements', 'nonfunctional', 'inputs', 'outputs', 'preconditions',
                'postconditions', 'dependencies', 'affected_modules', 'acceptance_criteria',
                'scenarios', 'skill_sources'):
        if not isinstance(contract.get(key), list):
            errors.append('Contract field must be a list: ' + key)
    if errors:
        return errors
    if 'browser_acceptance' in contract:
        acceptance=contract['browser_acceptance']
        if not isinstance(acceptance,dict):
            errors.append('browser_acceptance must be an object')
        else:
            if type(acceptance.get('required')) is not bool:
                errors.append('browser_acceptance.required must be a boolean')
            journeys=acceptance.get('journeys')
            if not isinstance(journeys,list) or any(not isinstance(j,str) or not j for j in journeys) or (acceptance.get('required') is True and not journeys):
                errors.append('Required browser journeys must be a nonempty list of IDs')
            if 'applies_to' in acceptance and (not isinstance(acceptance['applies_to'],list) or
                    not acceptance['applies_to'] or any(not isinstance(p,str) for p in acceptance['applies_to'])):
                errors.append('browser_acceptance.applies_to must list affected path patterns')
            if 'independent_review' in acceptance and type(acceptance['independent_review']) is not bool:
                errors.append('browser_acceptance.independent_review must be a boolean')
    if contract.get('risk') not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
        errors.append('Risk must be LOW/MEDIUM/HIGH/CRITICAL')
    if not isinstance(contract.get('mode'), str) or contract['mode'] not in MODES:
        errors.append('Evidence mode is invalid')
    if not isinstance(contract.get('review'), dict) or contract['review'].get('status') != 'REVIEWED':
        errors.append('Test plan must be reviewed; disclose whether review is independent')
    requirements = set()
    for requirement in contract['requirements']:
        if not isinstance(requirement, dict) or not isinstance(requirement.get('id'), str) or not requirement.get('description'):
            errors.append('Requirement must have a string ID and description'); continue
        if requirement['id'] in requirements:
            errors.append('Duplicate requirement ID: ' + requirement['id'])
        requirements.add(requirement['id'])
    scenarios = contract.get('scenarios', [])
    if not isinstance(scenarios, list):
        return errors + ['Scenarios must be a list']
    kinds = {s.get('kind') for s in scenarios if isinstance(s, dict)}
    mandatory = {'positive', 'negative', 'boundary', 'failure'}
    if contract.get('risk') in ('HIGH', 'CRITICAL'):
        mandatory |= {'security', 'performance'}
    for kind in sorted(mandatory - kinds):
        errors.append('Missing scenario kind: ' + kind)
    traced = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            errors.append('Invalid scenario'); continue
        if not isinstance(scenario.get('requirement'), str) or scenario.get('requirement') not in requirements:
            errors.append('Unknown requirement: ' + str(scenario.get('requirement')))
        else:
            traced.add(scenario['requirement'])
        if not scenario.get('expected'):
            errors.append('Scenario has no expected result')
        location, _, name = str(scenario.get('test', '')).partition('::')
        path = (root / location).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.suffix != '.py' or not name:
            errors.append('Missing executable test: ' + str(scenario.get('test'))); continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            names = set()
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    names.update(node.name + '.' + f.name for f in node.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(node.name)
            if name not in names:
                errors.append('Test symbol does not exist: ' + name)
        except (SyntaxError, UnicodeError):
            errors.append('Test source cannot be parsed: ' + location)
    if requirements - traced:
        errors.append('Untraced requirements: ' + ', '.join(sorted(requirements - traced)))
    return errors


def validate_promotion(head: str, base: str, human_approved: bool = False) -> list[str]:
    from .branch_policy import promotion_errors
    errors = promotion_errors(head, base)
    if base == 'main' and not human_approved:
        errors.append('Main requires owner-controlled release authorization')
    return errors


def validate_tdd(contract: dict, root: Path) -> list[str]:
    """Check stored actual RED/GREEN runner records. Never create expected-result evidence."""
    tdd = contract.get('tdd', {})
    if tdd.get('status') != 'RED_GREEN':
        return ['TDD RED/GREEN execution evidence is required']
    reports = {}
    try:
        for phase in ('red', 'green'):
            record = tdd[phase]
            path = (root / record['path']).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                return ['Missing or unsafe TDD artifact']
            if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                return ['Changed TDD artifact: ' + phase]
            reports[phase] = json.loads(path.read_text(encoding='utf-8'))
        red, green = reports['red'], reports['green']
        if not red.get('total') or not green.get('total') or red.get('passed') is not False or green.get('passed') is not True:
            return ['TDD must contain an actually failing RED and passing GREEN run']
        failures = {c['id'] for c in red.get('cases', []) if c.get('status') in ('FAIL','ERROR')}
        passes = {c['id'] for c in green.get('cases', []) if c.get('status') == 'PASS'}
        if not failures or not failures.issubset(passes) or any(c.get('status') != 'PASS' for c in green.get('cases', [])):
            return ['Every RED failure must execute and pass in GREEN; skips are not GREEN']
        if tdd['red'].get('exit_code') == 0 or tdd['green'].get('exit_code') != 0:
            return ['TDD process exit codes contradict the claimed result']
        return []
    except (KeyError, ValueError, TypeError, AttributeError, OSError):
        return ['Malformed TDD execution evidence']
