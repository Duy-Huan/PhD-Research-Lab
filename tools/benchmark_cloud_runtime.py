"""Isolated provider benchmark; --live explicitly runs trivial cloud inference.

Cold = first request in this process/workspace. Warm = same native session, fresh process.
No project documents, secrets, or existing research memory are read or sent.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true")
    p.add_argument("--providers", nargs="+", default=["codex", "claude_code", "gemini_cli"])
    p.add_argument("--app-server", action="store_true")
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--timeout", type=float, default=45)
    p.add_argument("--output", default="artifacts/cloud-runtime/benchmark.json")
    a = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="phdlab-bench-") as temp:
        os.environ["PHDLAB_DATA_DIR"] = temp
        from backend.core import config
        from backend.providers import cli as C, gateway as G
        config.save_config({"gateway": {"codex_app_server": a.app_server, "provider_timeout_s": a.timeout},
                            "memory": {"embed_engine": "hashing"}, "clearml": {"auto_record": False}})
        if not a.live:
            from providers.fakes import fake
            C.CONNECTORS.update({pid: fake(pid) for pid in a.providers})
            if a.app_server and "codex" in a.providers:
                C.CONNECTORS["codex"]._prefix = lambda: [sys.executable, str(ROOT / "tests/providers/fake_app_server.py")]
        report = {"live": a.live, "transport": "app-server" if a.app_server else "exec", "samples": [],
                  "definition": "cold=first request; warm=same workspace/native session, fresh CLI process; no daemon reuse"}
        for pid in a.providers:
            sid = ""
            for i in range(max(1, min(10, a.repeats))):
                start = time.perf_counter()
                sample = {"provider": pid, "run": "cold" if i == 0 else "warm"}
                try:
                    r = G.prepare("Reply only OK. Do not use tools or access files.", pid, session_id=sid, memory=False)
                    sid = r["session_id"]
                    G.send(r["id"])
                    cursor, received = 0, None
                    transport, fallback = "exec", False
                    while True:
                        batch = G.wait_events(r["id"], cursor, 1)
                        cursor = batch["next"]
                        for e in batch["events"]:
                            if e["type"] == "request_started":
                                transport = e.get("transport", "exec")
                            if e.get("state") == "transport_fallback":
                                fallback = True
                        if received is None and any(e["type"] == "text_delta" for e in batch["events"]):
                            received = round((time.perf_counter() - start) * 1000, 2)
                        if not batch["events"] and batch["status"] not in ("running", "starting", "ready"):
                            break
                    final = G.get(r["id"])
                    sample.update(status=final["status"], timings_ms=final["timings_ms"],
                                  consumer_first_token_ms=received, native_session=bool(final.get("provider_session")),
                                  resumed=bool(final.get("resume_session")), actual_transport=transport,
                                  transport_fallback=fallback, errors=final.get("errors", []))
                except Exception as e:
                    sample.update(status="unavailable", error=str(e)[:300])
                report["samples"].append(sample)
        dest = ROOT / a.output
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2), "utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
