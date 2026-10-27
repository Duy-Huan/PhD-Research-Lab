"""Conservative incremental selection; full/PR profiles never select a subset."""
from __future__ import annotations

import ast
from collections import defaultdict, deque
from pathlib import Path
import subprocess


def changed_files(root: Path, base: str) -> list[str]:
    """Include committed, staged, unstaged, renamed and untracked paths, NUL safely."""
    def git(*args: str) -> list[str]:
        return subprocess.check_output(['git', *args], cwd=root, timeout=30).decode('utf-8').split('\0')
    subprocess.run(['git', 'rev-parse', '--verify', base + '^{commit}'], cwd=root,
                   check=True, capture_output=True, timeout=30)
    paths = git('diff', '--no-renames', '--name-only', '-z', base, '--')
    paths += git('ls-files', '--others', '--exclude-standard', '-z')
    return sorted({p for p in paths if p and not p.startswith(('output/', 'artifacts/'))})


def select(root: Path, changed: list[str], profile: str) -> dict:
    def test_module(path: Path) -> str:
        return path.relative_to(root/'tests').with_suffix('').as_posix().replace('/','.')
    tests,live,unclassified = [],[],[]
    for path in sorted((root/'tests').rglob('test_*.py')):
        relative=path.relative_to(root/'tests')
        if relative.parts[0]=='live_e2e':
            live.append(path.relative_to(root).as_posix());continue
        directory=path.parent
        packaged=True
        while directory != root/'tests':
            if not (directory/'__init__.py').is_file():packaged=False;break
            directory=directory.parent
        if packaged:tests.append(test_module(path))
        else:unclassified.append(path.relative_to(root).as_posix())
    result = {'backend_tests': [], 'frontend': False, 'risk': 'LOW', 'reasons': [],
              'separate_live_tests':live,'blocked_tests':unclassified}
    def broad(reason: str, risk: str = 'HIGH') -> dict:
        result.update(backend_tests=tests, frontend=True, risk=risk)
        result['reasons'].append(reason)
        return result
    if profile in ('pr', 'full', 'release'):
        return broad('Mandatory independent full regression; incremental results cannot replace it', 'CRITICAL')
    if any(p.startswith(('.github/', 'backend/api/', 'backend/agent/', 'backend/providers/',
                         'backend/memory/', 'backend/core/')) for p in changed):
        return broad('Shared contract, security, memory, provider or CI policy changed', 'CRITICAL')
    if any(p in ('requirements.txt', 'requirements-dev.txt', 'requirements-ci.lock', 'frontend/package.json',
                 'frontend/package-lock.json', '.coveragerc') for p in changed):
        return broad('Dependency or coverage policy changed')
    relevant = []
    for p in changed:
        if p.startswith('frontend/'):
            result['frontend'] = True
        elif p.endswith('.py'):
            if not (root / p).is_file():
                return broad('Deleted Python dependency requires full fallback')
            relevant.append(p)
        elif p.endswith('.json') and p.startswith(('backend/', 'devtools/', 'tools/')):
            return broad('Runtime JSON/configuration semantics changed')
        elif not (p.endswith(('.md', '.json', '.csv', '.txt', '.svg', '.png', '.pdf', '.bib', '.tex'))
                  or p.startswith(('agent/', 'skills/', 'docs/'))):
            return broad('Unknown dependency semantics: ' + p)
    if not relevant:
        result['reasons'].append('Documentation only' if not result['frontend'] else 'Frontend suite is the conservative TS dependency boundary')
        return result
    modules = {}
    reverse = defaultdict(set)
    for folder in ('backend', 'tools', 'scripts', 'devtools', 'tests'):
        for path in (root / folder).rglob('*.py'):
            rel = path.relative_to(root).as_posix()
            module = rel[:-3].replace('/', '.')
            if module.endswith('.__init__'):
                module = module[:-9]
            modules[module] = rel
    for module, rel in modules.items():
        try:
            tree = ast.parse((root / rel).read_text(encoding='utf-8-sig'))
        except (SyntaxError, UnicodeError):
            return broad('Unparseable dependency graph requires full fallback')
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ''
                if node.level:
                    package = module if rel.endswith('/__init__.py') else module.rpartition('.')[0]
                    parts = package.split('.')
                    prefix = '.'.join(parts[:len(parts) - node.level + 1] + ([prefix] if prefix else []))
                imports = [prefix] + [prefix + '.' + alias.name for alias in node.names]
            for dependency in imports:
                if dependency in modules:
                    reverse[dependency].add(module)
    seeds = {m for m, p in modules.items() if p in relevant}
    visited, queue = set(seeds), deque(seeds)
    while queue:
        for dependent in reverse[queue.popleft()]:
            if dependent not in visited:
                visited.add(dependent); queue.append(dependent)
    selected = sorted({test_module(root/modules[m]) for m in visited
                       if modules[m].startswith('tests/') and Path(modules[m]).name.startswith('test_')
                       and test_module(root/modules[m]) in tests})
    if not selected or any(p not in modules.values() for p in relevant):
        return broad('No provable test dependency; full fallback rather than zero tests')
    # Dynamic module loading cannot be proved by AST. Such runtime changes broaden scope.
    if any(p.startswith(('backend/', 'tools/')) and ('importlib' in (root/p).read_text(encoding='utf-8-sig')
           or '__import__' in (root/p).read_text(encoding='utf-8-sig')) for p in relevant):
        return broad('Dynamic import boundary changed')
    result['backend_tests'] = selected
    result['risk'] = 'MEDIUM'
    result['reasons'].append('Reverse transitive Python imports, including relative and from-package imports')
    return result
