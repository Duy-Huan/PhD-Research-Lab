"""v4.2 acceptance: the browser UI and the `phdlab` CLI are two clients of ONE running backend, used at the same time.
Starts a real server process (uvicorn, throw-away data folder), drives it from CLI processes (also through the
phdlab.bat / phdlab launcher) and from an HTTP client that behaves like the UI, and checks that each side sees the
other's changes (sessions, code projects, the /api/events bus)."""
import _env  # noqa: F401  (must be first)
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import httpx

ROOT = _env.ROOT


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]




if __name__ == "__main__":
    unittest.main()
