"""Fake connectors for the provider tests (import _env first)."""
import _env  # noqa: F401  (must be first: throw-away data folder)
import os
import sys

from backend.providers import cli as C

FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_cli.py")
FMT = {"codex": "codex", "claude_code": "claude", "antigravity": "agy", "gemini_cli": "gemini"}


def fake(pid: str, mode: str = "ok"):
    """A real connector class whose binary is the fake CLI (everything else — env, stdin, parsing — is the real code)."""
    base = type(C.CONNECTORS[pid])

    class Fake(base):
        def binary(self):
            return sys.executable

        def _probe(self):
            return {"bin": sys.executable, "ok": True, "version": "fake 1.0", "login_code": 0, "login": "Logged in using ChatGPT"}

        def argv(self, context):
            super().argv(context)  # the real argument builder must not fail
            return [sys.executable, FAKE, FMT[pid], mode]
    return Fake()
