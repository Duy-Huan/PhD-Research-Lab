"""Explicit local entrypoint; importing CI/PR content never starts a coding agent."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from devtools.verification.ci_repair import main

if __name__ == '__main__': raise SystemExit(main())
