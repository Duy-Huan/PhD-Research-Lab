"""Canonical entrypoint: python scripts/verify.py --profile quick|feature|pr|full|targeted."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from devtools.verification.runner import main

if __name__ == '__main__':
    raise SystemExit(main())
