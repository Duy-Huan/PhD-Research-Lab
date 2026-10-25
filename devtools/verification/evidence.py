"""Compact failure evidence and a durable, fail-closed three-repair budget."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


def fingerprints(cases: list[dict]) -> list[dict]:
    groups = {}
    for case in cases:
        if case.get('status') not in ('FAIL', 'ERROR', 'BLOCKED', 'SKIP', 'NOT_RUN'):
            continue
        detail = str(case.get('details') or case.get('reason') or case.get('status'))
        lines = [line.strip() for line in detail.splitlines() if line.strip()]
        # Python prints the originating exception before wrappers in chained tracebacks.
        candidates = [line for line in lines if re.match(r'[\w.]+(?:Error|Exception):', line)]
        cause = (candidates[0] if candidates else lines[-1] if lines else 'Unknown failure')[:1000]
        cause = re.sub(r'0x[0-9a-fA-F]+', '<address>', cause)
        key = hashlib.sha256((str(case.get('status')) + ':' + cause).encode()).hexdigest()[:16]
        group = groups.setdefault(key, {'fingerprint': key, 'cause': cause, 'count': 0,
                                      'status':case.get('status'),
                                      'case_ids': [], 'classification': 'UNCLASSIFIED',
                                      'diagnosis': 'Heuristic grouping; inspect raw evidence before repairing'})
        group['count'] += 1; group['case_ids'].append(case.get('id', 'unknown'))
        if any(word in cause.lower() for word in ('connection refused', 'connecterror', 'timeout')):
            group['classification'] = 'ENVIRONMENT_OR_DEPENDENCY'
        elif 'AssertionError' in cause:
            group['classification'] = 'BEHAVIOR_ASSERTION'
        elif 'ModuleNotFoundError' in cause or 'SyntaxError' in cause:
            group['classification'] = 'DEPENDENCY_OR_COMPATIBILITY'
    priority={'FAIL':0,'ERROR':0,'BLOCKED':1,'NOT_RUN':2,'SKIP':3}
    return sorted(groups.values(), key=lambda g: (priority.get(g['status'],2),-g['count'],g['fingerprint']))


def aggregate(states: dict[str, str], required: list[str]) -> str:
    values = [states.get(name, 'MISSING') for name in required]
    if not values:
        return 'BLOCKED'
    if any(v == 'FAIL' for v in values):
        return 'FAIL'
    return 'PASS' if all(v == 'PASS' for v in values) else 'BLOCKED'


class RepairBudget:
    """A key is the task/PR identity, never the changing head SHA or run identifier."""
    def __init__(self, path: Path, key: str):
        self.path, self.key = path, key

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(value, dict):
                raise ValueError('Invalid repair ledger')
            for item in value.values():
                if not isinstance(item, dict) or not isinstance(item.get('attempts'), int) or not 0 <= item['attempts'] <= 3:
                    raise ValueError('Invalid repair counter')
            return value
        except (ValueError, OSError) as exc:
            raise ValueError('Repair ledger unreadable; preserve it and stop') from exc

    @property
    def attempts(self) -> int:
        return self._load().get(self.key, {}).get('attempts', 0)

    def can_repair(self) -> bool:
        return self.attempts < 3

    def _save(self, value: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        temp.replace(self.path)

    def record_failure(self, sha: str) -> dict:
        value = self._load(); prior = value.get(self.key, {'attempts': 0, 'history': []})
        if prior['attempts'] >= 3:
            raise RuntimeError('Three failed repair cycles exhausted; stop and report')
        item = {'attempts': prior['attempts'] + 1, 'history': prior['history'] + [{'sha': sha, 'status': 'FAIL'}]}
        value[self.key] = item; self._save(value)
        return item

    def record_success(self, sha: str) -> None:
        value = self._load(); item = value.get(self.key, {'attempts': 0, 'history': []})
        item['history'].append({'sha': sha, 'status': 'PASS'})
        value[self.key] = item; self._save(value)
