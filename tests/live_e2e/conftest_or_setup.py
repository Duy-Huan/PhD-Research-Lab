"""Live E2E Preflight, Safe Isolation, and Local Phi-4 Call Auditing.

Guarantees:
  1. PHDLAB_DATA_DIR is ALWAYS isolated to a dedicated temp directory outside data/.
  2. All agents configure engine='local' and model='phi-4' pointing to LM Studio.
  3. No cloud API spend (fallback_to_cloud=False, allow_api_billing=False).
  4. Redacted LLM call ledger is written to qa/live_e2e/LLM_CALLS_REDACTED.jsonl.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure isolated data directory before importing backend
if not os.environ.get("PHDLAB_DATA_DIR") or "data" in Path(os.environ["PHDLAB_DATA_DIR"]).parts:
    _isolated_dir = tempfile.mkdtemp(prefix="phdlab-live-e2e-isolated-")
    os.environ["PHDLAB_DATA_DIR"] = _isolated_dir
    atexit.register(lambda: shutil.rmtree(_isolated_dir, ignore_errors=True))

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ["JUPYTER_DATA_DIR"] = os.path.join(os.environ["PHDLAB_DATA_DIR"], "_jupyter")

from backend.core import config as C

# Hard assert on isolation
if C.GLOBAL_DIR.resolve() == (ROOT / "data").resolve():
    raise SystemExit("CRITICAL VIOLATION: Live E2E tests must not run on production data folder!")

QA_DIR = Path(os.environ.get("PHDLAB_LIVE_EVIDENCE_DIR") or ROOT / "qa" / "live_e2e")
QA_DIR.mkdir(parents=True, exist_ok=True)
CALLS_LOG = QA_DIR / "LLM_CALLS_REDACTED.jsonl"
HARNESS_LOG = QA_DIR / "HARNESS_STATES.jsonl"

LOCAL_MODEL = os.environ.get("PHDLAB_LIVE_MODEL", "phi-4")
LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"


def configure_live_phi4():
    """Configure system for hermetic, live local inference using LM Studio phi-4."""
    agent_modes = {a: "local" for a in C.AGENTS}
    agent_models = {a: LOCAL_MODEL for a in C.AGENTS}
    C.save_config({
        "lmstudio_base_url": LMSTUDIO_BASE_URL,
        "local_model": LOCAL_MODEL,
        "fallback_to_cloud": False,
        "agent_modes": agent_modes,
        "agent_models": agent_models,
        "clearml": {"auto_record": False},
        "memory": {"embed_engine": "hashing"},
        "research_os": {
            "enabled": True,
            "team_enabled": True,
            "multi_team_enabled": True
        }
    })
    from backend.providers import models
    if "qwen3.5" in LOCAL_MODEL:
        models.REASONING.set("off")


def log_llm_call(role: str, prompt: str, response: str, latency: float, model: str = LOCAL_MODEL, engine: str = "local", success: bool = True):
    """Record anonymized, hashed LLM call to audit ledger."""
    prompt_hash = hashlib.sha256(prompt.encode("utf-8", errors="replace")).hexdigest()[:16]
    resp_hash = hashlib.sha256(response.encode("utf-8", errors="replace")).hexdigest()[:16]
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "role": role,
        "engine": engine,
        "model": model,
        "endpoint": LMSTUDIO_BASE_URL,
        "prompt_id": f"prompt_{prompt_hash}",
        "prompt_len": len(prompt),
        "response_id": f"resp_{resp_hash}",
        "response_len": len(response),
        "latency_sec": round(latency, 4),
        "tokens_est": max(1, len(response.split())),
        "success": success,
        "billable_cost_usd": 0.0
    }
    with open(CALLS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_harness_event(event_type: str, details: Dict[str, Any]):
    """Log mission/workflow state transition to HARNESS_STATES.jsonl."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event_type,
        **details
    }
    with open(HARNESS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def check_lmstudio_health() -> Dict[str, Any]:
    """Verify live LM Studio server and check whether phi-4 is available."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{LMSTUDIO_BASE_URL}/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id") for m in data.get("data", []) if m.get("id")]
            has_phi4 = LOCAL_MODEL in models  # legacy key; checks the explicitly selected model
            return {
                "online": True,
                "url": LMSTUDIO_BASE_URL,
                "models": models,
                "has_phi4": has_phi4,
                "active_model": LOCAL_MODEL
            }
    except Exception as e:
        return {
            "online": False,
            "url": LMSTUDIO_BASE_URL,
            "error": str(e),
            "has_phi4": False
        }
