"""Compact, conservative defect handoff. Observations never certify a repair."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def _proof(record: dict, root: Path | None) -> bool:
    if root is None or not isinstance(record, dict):
        return False
    try:
        path = (root / record['artifact']).resolve()
        return (path.is_relative_to(root.resolve()) and path.is_file()
                and hashlib.sha256(path.read_bytes()).hexdigest() == record.get('sha256'))
    except (KeyError, TypeError, OSError):
        return False


def defect_report(findings: list[dict], source: str, mode: str, artifacts_root: Path | None = None) -> dict:
    defects = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError('Defect observation must be an object')
        reproduction = finding.get('reproduction', {})
        regression = finding.get('regression', {})
        reproduced = reproduction.get('status') == 'REPRODUCED' and _proof(reproduction, artifacts_root)
        fixed = (reproduced and regression.get('test') and regression.get('before') == 'FAIL'
                 and regression.get('after') == 'PASS' and regression.get('source_sha256') == source
                 and _proof(regression, artifacts_root))
        status = 'FIXED' if fixed else 'CONFIRMED' if reproduced else 'UNCONFIRMED'
        fingerprint = hashlib.sha256(json.dumps({k: finding.get(k) for k in ('title', 'expected', 'actual')},
                                                sort_keys=True).encode()).hexdigest()[:16]
        defects.append({**finding, 'id': 'UAT-' + fingerprint, 'status': status, 'mode': mode,
                        'source_sha256': source, 'production_fix': bool(fixed and mode != 'MOCKED'),
                        'classification': finding.get('classification', 'UNCLASSIFIED')})
    return {'schema_version': 1, 'source_sha256': source, 'mode': mode, 'defects': defects,
            'unresolved': sum(d['status'] != 'FIXED' for d in defects),
            'claims_fixed': any(d['production_fix'] for d in defects),
            'limitation': 'Proof hashes preserve supplied records; independent acceptance review remains separate'}
