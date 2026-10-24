"""Reject deletions/renames out of skills/ and agent/ in staged or CI changes."""
import argparse
from pathlib import PurePosixPath
import subprocess


def violations(changes: str) -> list[str]:
    errors = []
    for line in changes.splitlines():
        fields = line.split('\t')
        if len(fields) < 2:
            continue
        status, source = fields[:2]
        protected = PurePosixPath(source).parts[:1] in (('skills',), ('agent',))
        if protected and (status == 'D' or (status.startswith('R') and PurePosixPath(fields[-1]).parts[:1] != PurePosixPath(source).parts[:1])):
            errors.append(source)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', help='CI diff base; omit to inspect staged changes')
    args = parser.parse_args()
    command = ['git', 'diff', '--name-status', '-M', args.base, 'HEAD'] if args.base else ['git', 'diff', '--cached', '--name-status', '-M']
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    errors = violations(result.stdout)
    for path in errors:
        print('PROTECTED_RESOURCE_DELETION: ' + path)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
