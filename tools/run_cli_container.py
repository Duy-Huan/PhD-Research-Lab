"""Entry point opened in a visible terminal only after a user launches a native provider."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.providers.isolated_cli import run

if __name__ == '__main__':
    raise SystemExit(run(Path(sys.argv[1]), interactive='--headless' not in sys.argv))
