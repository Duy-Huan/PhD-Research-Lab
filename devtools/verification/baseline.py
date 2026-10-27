"""Validate evidence-backed issue accounting. This module never waives test results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


def validate_baseline(path: Path, root: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ['Known-issues baseline is missing or unreadable']
    if not isinstance(data, dict):
        return ['Known-issues baseline must be an object']
    errors = []
    if data.get('schema_version') != 1 or not re.fullmatch(r'[0-9a-f]{40}', str(data.get('baseline_sha', ''))):
        errors.append('Baseline must identify schema 1 and an exact commit SHA')
    # No exception has been explicitly approved. A JSON approval claim is not authorization.
    if data.get('exceptions') != []:
        errors.append('No baseline exceptions are authorized; mandatory failures remain blocking')
    issues = data.get('issues')
    if not isinstance(issues, list) or not issues:
        return errors + ['Known-issues baseline must contain issue records']
    seen = set()
    for issue in issues:
        if not isinstance(issue, dict):
            errors.append('Issue must be an object'); continue
        name = issue.get('id')
        if not isinstance(name, str) or not name or name in seen:
            errors.append('Issue IDs must be nonempty and unique')
        else:
            seen.add(name)
        for field in ('classification', 'status', 'owner', 'remediation'):
            if not isinstance(issue.get(field), str) or not issue[field].strip():
                errors.append(f'Issue {name} requires {field}')
        if issue.get('severity') not in ('P0', 'P1', 'P2', 'P3'):
            errors.append(f'Issue {name} requires a valid severity')
        evidence = issue.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            errors.append(f'Issue {name} requires raw evidence'); continue
        for record in evidence:
            try:
                target = (root/record['path']).resolve()
                if not target.is_relative_to(root.resolve()) or not target.is_file():
                    raise ValueError('Unsafe or missing evidence')
                if hashlib.sha256(target.read_bytes()).hexdigest() != record['sha256']:
                    raise ValueError('Evidence digest mismatch')
            except (KeyError, TypeError, ValueError, OSError):
                errors.append(f'Issue {name} evidence is missing, unsafe or changed')
    return errors
