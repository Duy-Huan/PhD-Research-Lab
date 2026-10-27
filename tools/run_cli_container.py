"""Entry point opened in a visible terminal only after a user launches a native provider."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.providers.isolated_cli import run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--runtime-owner')
    args = parser.parse_args()
    raise SystemExit(run(args.plan, interactive=not args.headless, runtime_owner=args.runtime_owner))
