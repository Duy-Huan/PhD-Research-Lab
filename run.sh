#!/usr/bin/env bash
# Linux / macOS launcher for PhD Interactive Autonomous Research Lab
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then PY=python3
else echo "[ERROR] python3 not found. Install it, e.g.: sudo apt install python3 python3-venv"; exit 1; fi
exec "$PY" start.py "$@"
