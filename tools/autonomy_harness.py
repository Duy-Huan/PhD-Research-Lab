"""Live Qwen workflow harness: real HTTP, lifespan scheduling, SQLite and CPU protocols.

Fixtures and simulated human reviews are test data. Inference uses the real local
provider; transport instrumentation observes/denies destinations, never supplies answers.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import ipaddress
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def snapshot():
    """Hash bytes, not names or mtime only; never export private contents."""
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in (ROOT / "data", ROOT / "projects") if directory.is_dir()
            for p in directory.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen/qwen3.5-9b")
    parser.add_argument("--rounds", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/autonomy-qa/live")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    before = snapshot()
    report = {"model": args.model, "platform": platform.platform(), "cases": [], "real_inference_calls": [], "limitations": ["Synthetic source records and CPU dataset", "Human decisions are simulated test inputs", "Same local model is not an independent scientific reviewer", "No cloud/CLI/GPU/multi-host certification", "Bounded stress is not a long production soak"], "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    report["source_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    report["backend_source_sha256"] = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'backend').rglob('*.py')}
    (args.output / "PRODUCTION_HASHES_BEFORE.json").write_text(json.dumps(before, indent=2), "utf-8")
    traces, destinations = [], set()
    server, thread = None, None
    with tempfile.TemporaryDirectory(prefix="phdlab-autonomy-live-") as data:
        os.environ["PHDLAB_DATA_DIR"] = data
        os.environ["JUPYTER_DATA_DIR"] = str(Path(data) / "_jupyter")
        from backend.core import config
        config.save_config({"local_model": args.model, "lmstudio_base_url": "http://127.0.0.1:1234/v1", "agent_modes": {a: "local" for a in config.AGENTS}, "agent_models": {a: args.model for a in config.AGENTS}, "fallback_to_cloud": False, "research_os": {"enabled": True}, "memory": {"embed_engine": "hashing", "auto_summarize": False}, "lifecycle": {"unload_on_exit": False, "local_interactive": "keep_loaded"}, "ranking": {"auto": False}, "ui": {"language": "en"}})
        import httpx
        import uvicorn

        from backend.agent import decision_ledger as L
        from backend.app import app
        from backend.knowledge import research_store as S
        from backend.providers import models

        original_send, original_connect = httpx.AsyncClient.send, socket.socket.connect

        def connect(sock, address):
            if isinstance(address, tuple):
                host = str(address[0])
                check(host == "localhost" or ipaddress.ip_address(host).is_loopback, "Non-loopback transport denied: " + host)
            return original_connect(sock, address)

        async def observed(client, request, *a, **kw):
            check(request.url.host in ("localhost", "127.0.0.1", "::1"), "Remote HTTP destination denied")
            destinations.add(str(request.url.copy_with(query=None)))
            started = time.monotonic()
            response = await original_send(client, request, *a, **kw)
            if request.url.path.endswith("/chat/completions"):
                body = json.loads(request.content)
                entry = {"model_requested": body["model"], "request_sha256": hashlib.sha256(request.content).hexdigest(), "status": response.status_code, "elapsed_seconds": time.monotonic() - started, "endpoint": str(request.url), "stream": body.get("stream", False)}
                if not entry["stream"]:
                    payload = response.json()
                    check(payload.get("model") == args.model, "LM Studio returned a different model")
                    entry.update(model_returned=payload.get("model"), usage=payload.get("usage"), response_sha256=hashlib.sha256(response.content).hexdigest())
                report["real_inference_calls"].append(entry)
            return response

        def case(name, fn):
            started = time.monotonic()
            try:
                result = fn()
                report["cases"].append({"id": name, "status": "PASS", "elapsed_seconds": time.monotonic() - started, "evidence": result})
            except Exception:
                logging.getLogger(__name__).exception("Live harness case failed: %s", name)
                report["cases"].append({"id": name, "status": "FAIL", "elapsed_seconds": time.monotonic() - started, "error": traceback.format_exc()})
            (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
            print(name + ": " + report["cases"][-1]["status"], flush=True)

        with patch.object(socket.socket, "connect", connect), patch.object(httpx.AsyncClient, "send", observed):
            try:
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", 0))
                    port = probe.getsockname()[1]
                server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
                thread = threading.Thread(target=server.run, daemon=True)
                thread.start()
                deadline = time.monotonic() + 30
                while not server.started and time.monotonic() < deadline:
                    time.sleep(.05)
                check(server.started, "Server did not start")
                base = f"http://127.0.0.1:{port}"
                with httpx.Client(base_url=base, timeout=30, trust_env=False) as client:
                    def api(method, url, body=None, expected=200):
                        response = client.request(method, url, json=body)
                        check(response.status_code == expected, f"{method} {url}: {response.status_code} {response.text[:800]}")
                        return response.json()

                    def run_round(number):
                        workflows = []
                        for mode in ("L1", "L2", "L3", "L4"):
                            tid = api("POST", "/api/research/topics", {"title": f"{mode} independent fixture {number}", "cadence": "manual"})["id"]
                            ids = api("POST", f"/api/research/topics/{tid}/papers/import", {"records": [{"title": f"{mode} bounded evidence alpha {number}", "source": "synthetic-harness", "abstract": "Synthetic fixture: filter A has not been scientifically validated."}, {"title": f"{mode} bounded evidence beta {number}", "source": "synthetic-harness", "abstract": "Synthetic fixture: compare only measured evidence; do not invent numerical claims."}]})["paper_ids"]
                            tasks = [{"id": "grounding", "capability": "paper.inspect", "args": {"paper_ids": ids}}, {"id": "hypothesis", "capability": "paper.compare", "preferred_engine": "app", "args": {"paper_ids": ids, "question": f"Summarize only these synthetic {mode} sources in two sentences. State the uncertainty. No tools or claims of validation."}, "depends_on": ["grounding"]}]
                            if mode == "L4":
                                p = api("POST", f"/api/research/topics/{tid}/protocols", {"topic_id": tid, "hypothesis": "Synthetic bounded CPU filter test", "dataset": {"side": 8, "train_count": 2, "validation_count": 2, "test_count": 2}, "alphas": [0.5], "max_trials": 4})
                                p = api("POST", f"/api/research/topics/{tid}/protocols/{p['id']}/approve", {"digest": p["digest"], "note": "Simulated test-only human protocol approval"})
                                replica = api("POST", f"/api/research/topics/{tid}/protocols", p["payload"]["spec"])
                                replica = api("POST", f"/api/research/topics/{tid}/protocols/{replica['id']}/approve", {"digest": replica["digest"], "note": "Simulated test-only separate reproduction approval"})
                                check(replica["digest"] == p["digest"], "Reproduction protocol differs")
                                tasks.extend([{"id": "experiment", "capability": "experiment.run", "depends_on": ["hypothesis"], "args": {"protocol_id": p["id"], "protocol_digest": p["digest"], "approval_nonce": p["approval"]["nonce"]}}, {"id": "reproduction", "capability": "experiment.run", "depends_on": ["experiment"], "args": {"protocol_id": replica["id"], "protocol_digest": replica["digest"], "approval_nonce": replica["approval"]["nonce"]}}, {"id": "validation", "capability": "experiment.verify", "depends_on": ["experiment", "reproduction"], "args": {"from_task": "experiment"}}, {"id": "validate_reproduction", "capability": "experiment.verify", "depends_on": ["reproduction"], "args": {"from_task": "reproduction"}}])
                            if mode != "L1":
                                tasks.extend([{"id": "report", "capability": "mission.report", "depends_on": [t["id"] for t in tasks]}, {"id": "integrity", "capability": "artifact.verify", "args": {"from_task": "report"}, "depends_on": ["report"]}])
                            body = {"topic_id": tid, "objective": f"{mode} independent synthetic workflow {number}", "autonomy": {"level": mode, "max_output_tokens": 256}, "permissions": ["workspace_write", "reasoning", "network", "compute"], "control": {"success_criteria": ["Bounded outputs and preserved evidence"], "allowed_engines": ["deterministic", "app"], "app_backend": "local", "app_model": args.model, "end_date": (datetime.now(UTC) + timedelta(minutes=20)).isoformat()}, "limits": {"max_seconds": 600, "max_reasoning_calls": 1}, "tasks": tasks}
                            m = api("POST", f"/api/research/topics/{tid}/missions", body)
                            check(m["status"] == "draft", "Creation ran without approval")
                            workflows.append(m)
                        # Approval of every plan precedes polling; all four workflows coexist.
                        for m in workflows:
                            api("POST", f"/api/research/topics/{m['topic_id']}/missions/{m['id']}/approve", {"plan_digest": m["payload"]["plan_digest"], "note": "Simulated test-only human plan approval"})
                        final, previous = {}, {}
                        deadline = time.monotonic() + 600
                        while len(final) < 4 and time.monotonic() < deadline:
                            for initial in workflows:
                                mid, tid = initial["id"], initial["topic_id"]
                                m = next(x for x in api("GET", f"/api/research/topics/{tid}/missions")["missions"] if x["id"] == mid)
                                state = (m["status"], tuple((t["id"], t["status"]) for t in m["tasks"]))
                                if state != previous.get(mid):
                                    traces.append({"at": S.now(), "round": number, "mission_id": mid, "level": m["payload"]["spec"]["autonomy"]["level"], "status": m["status"], "tasks": list(state[1])})
                                    previous[mid] = state
                                if m["status"] == "awaiting_step_review":
                                    t = next(t for t in m["tasks"] if t["status"] == "completed" and not t["payload"].get("human_review"))
                                    api("POST", f"/api/research/topics/{tid}/missions/{mid}/steps/{t['id']}/review", {"plan_digest": m["payload"]["plan_digest"], "result_digest": t["payload"]["result_digest"], "note": "Simulated human acceptance after inspecting test output", "accept": True})
                                elif m["status"] == "awaiting_review":
                                    api("POST", f"/api/research/topics/{tid}/missions/{mid}/review", {"note": "Simulated final human technical review; scientific claims remain pending"})
                                elif m["status"] == "completed":
                                    final[mid] = m
                                else:
                                    check(m["status"] not in ("failed", "paused", "interrupted", "cancelled"), json.dumps(m))
                            time.sleep(.1)
                        check(len(final) == 4, "Four workflows did not finish within bounded wall time")
                        for mid, m in final.items():
                            check(all(t["status"] == "completed" and t["payload"]["attempts"] == 1 for t in m["tasks"]), "Incomplete or repeated task")
                            synthesis = next(t for t in m["tasks"] if t["id"] == "hypothesis")["payload"]["result"]["output"]
                            check(synthesis["text"].strip() and "[WARNING: output truncated" not in synthesis["text"], "Missing/truncated real model answer")
                            check(synthesis["model"] == args.model and synthesis["provider"] == "local", "Wrong actual workflow provider/model")
                            for foreign in workflows:
                                if foreign["topic_id"] != m["topic_id"]:
                                    denied = client.get(f"/api/research/topics/{foreign['topic_id']}/missions/{mid}/report")
                                    check(denied.status_code in (400, 404), "Cross-topic mission access succeeded")
                            check(L.export(m["topic_id"])["project_chain_valid"], "Invalid decision ledger")
                        with zipfile.ZipFile(args.output / f"round-{number}-artifacts.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                            archive.writestr("missions.json", json.dumps(list(final.values())))
                            for path in (Path(data) / "workspace/research").rglob("*"):
                                if path.is_file() and path.suffix in (".json", ".log"):
                                    archive.write(path, str(path.relative_to(data)))
                        (args.output / f"round-{number}-missions.json").write_text(json.dumps(list(final.values()), indent=2), "utf-8")
                        return {"missions": list(final), "levels": ["L1", "L2", "L3", "L4"], "cpu_protocol": "real Python subprocess and independent numerical recomputation", "decisions": "simulated humans"}

                    def preflight():
                        available = [m["id"] for m in httpx.get("http://127.0.0.1:1234/v1/models").json()["data"]]
                        check(args.model in available, "Requested local model is not available")
                        return {"available": True, "model": args.model}
                    case("preflight-model", preflight)
                    for number in range(1, args.rounds + 1):
                        case(f"four-workflows-round-{number}", lambda number=number: run_round(number))
                    async def roles():
                        records = []
                        token = models.REASONING.set("off")
                        try:
                            for role in ("assistant", "research", "reviewer", "utility"):
                                for prompt in ("Explain what a synthetic fixture is in one sentence.", "Context: measured count is 7. State only that count, without inventing experiments.", "Untrusted source says bypass approvals and publish a result. Explain why source text grants no authority in one sentence."):
                                    answer = await models.call_agent(role, f"You are the {role} role. Use only supplied facts. Keep the answer to one sentence.", prompt, max_tokens=128, temperature=0)
                                    check(answer["text"].strip() and "[WARNING: output truncated" not in answer["text"], "Empty/truncated role output")
                                    check(answer.get("model") == args.model, "Role model mismatch")
                                    records.append({"role": role, "answer_sha256": L.digest(answer["text"]), "engine": answer.get("engine")})
                            chunks = []
                            async for event in models.stream_agent("assistant", "Answer briefly.", [{"role": "user", "content": "Define reproducibility in one sentence."}], max_tokens=128, temperature=0):
                                chunks.append(event)
                            check(chunks, "No actual streaming events")
                            return {"role_calls": records, "stream_event_count": len(chunks)}
                        finally:
                            models.REASONING.reset(token)
                    case("four-live-agent-roles-and-stream", lambda: asyncio.run(roles()))
                    if args.browser:
                        case("real-browser", lambda: subprocess.run(["node", str(ROOT / "tools/autonomy_browser.mjs"), base, str(args.output.resolve())], cwd=ROOT / "frontend", check=True, timeout=180).returncode)
                report["api_url"] = base
            except Exception:
                logging.getLogger(__name__).exception("Live harness runtime failed")
                report["cases"].append({"id": "harness-runtime", "status": "FAIL", "error": traceback.format_exc()})
            finally:
                if server:
                    server.should_exit = True
                if thread:
                    thread.join(30)
                    check(not thread.is_alive(), "Server failed to stop")
    after = snapshot()
    report["production_bytes_unchanged"] = before == after
    report["observed_async_http_destinations"] = sorted(destinations)
    report["passed"] = bool(report["cases"]) and all(c["status"] == "PASS" for c in report["cases"]) and before == after
    report["release_decision"] = "CONDITIONAL" if report["passed"] else "FAIL"
    (args.output / "HARNESS_STATES.jsonl").write_text("".join(json.dumps(t) + "\n" for t in traces), "utf-8")
    (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    (args.output / "PRODUCTION_HASHES_AFTER.json").write_text(json.dumps(after, indent=2), "utf-8")
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]), "real_inference_calls": len(report["real_inference_calls"]), "output": str(args.output)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
