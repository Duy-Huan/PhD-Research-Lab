"""Isolated installed-server conformance probe. No model work, account login or API-key sharing."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-path", help="Audited upstream tooling/sdk/python source folder, if the optional SDK is not installed")
    parser.add_argument("--output", default="artifacts/openscience-audit/live-protocol.json")
    args = parser.parse_args()
    if args.sdk_path:
        sys.path.insert(0, str(Path(args.sdk_path).resolve()))
    report = {"model_work_submitted": False, "status": "unavailable"}
    from backend.execution.tools import node_argv, which, NO_WINDOW
    from backend.providers.cli import kill_tree
    from backend.providers.cli_space import minimal_env
    from backend.core.telemetry import redact
    from backend.research_engines.openscience import OpenScienceEngine, Settings, policy
    proc = None
    with tempfile.TemporaryDirectory(prefix="phdlab-openscience-live-") as temp:
        root = Path(temp)
        workspace = root / "workspace"
        workspace.mkdir()
        env = minimal_env()
        token = secrets.token_urlsafe(32)
        env.update(OPENSCIENCE_AUTH_TOKEN=token, OPENSCIENCE_DATA_DIR=str(root / "data"),
                   OPENSCIENCE_CONFIG_DIR=str(root / "config"), OPENSCIENCE_TEST_HOME=str(root),
                   OPENSCIENCE_DISABLE_AUTOUPDATE="1", OPENSCIENCE_CONFIG_CONTENT=json.dumps({"permission": policy(False)}))
        for key, folder in (("XDG_DATA_HOME", "xdg-data"), ("XDG_CACHE_HOME", "xdg-cache"),
                            ("XDG_CONFIG_HOME", "xdg-config"), ("XDG_STATE_HOME", "xdg-state")):
            env[key] = str(root / folder)
        try:
            from openscience import Client, CursorError, HTTPError
            binary = which("openscience")
            if not binary:
                raise RuntimeError("Installed OpenScience CLI was not found")
            argv = node_argv(binary, "@synsci/openscience/bin/openscience")
            # Audited network.ts binds loopback internally; --hostname is not supported.
            proc = subprocess.Popen(argv + ["serve", "--port", "0", "--format", "json"],
                                    cwd=workspace, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
                                    start_new_session=os.name != "nt")
            output, errors, lines = queue.Queue(), [], []
            def drain_stdout():
                for line in proc.stdout:
                    lines.append(redact(line)[:300])
                    del lines[:-8]
                    output.put(line)
            def drain_stderr():
                for line in proc.stderr:
                    errors.append(redact(line)[:300])
                    del errors[:-8]
            readers = [threading.Thread(target=drain_stdout, daemon=True), threading.Thread(target=drain_stderr, daemon=True)]
            for reader in readers:
                reader.start()
            end, ready = time.monotonic() + 30, None
            while time.monotonic() < end:
                try:
                    line = output.get(timeout=0.2)
                except queue.Empty:
                    if proc.poll() is not None:
                        break
                    continue
                try:
                    value = json.loads(line)
                    if value.get("type") == "server.ready":
                        ready = value
                        break
                except ValueError:
                    continue
            if not ready:
                for reader in readers:
                    reader.join(timeout=0.5)
                report.update(exit_code=proc.poll(), stdout=lines, stderr=errors)
                raise RuntimeError("Installed server did not emit a readiness record")
            client = Client(ready["url"], token=token, directory=str(workspace), timeout=5)
            report["server_version"] = ready["version"]
            report["capabilities"] = client.capabilities()
            try:
                Client(ready["url"], token="invalid-test-token", timeout=5).capabilities()
            except HTTPError as error:
                if error.status != 401:
                    raise
                report["deployment_auth_checked"] = True
            else:
                raise RuntimeError("Invalid deployment token was accepted")
            engine = OpenScienceEngine()
            cfg = Settings(base_url=ready["url"], token=token)
            engine.verify_policy(cfg, str(workspace))
            with engine.http(cfg, str(workspace)) as http:
                if engine.public_json(http, "/file/artifact-store", params={"state": "active"}) != []:
                    raise RuntimeError("Isolated runtime unexpectedly has artifacts")
            report.update(effective_policy_checked=True, artifact_inventory_checked=True)
            session = client.create_session(title="PhD Lab protocol conformance", workspace="project")
            snapshot = client.snapshot(session["id"])
            replay = client.replay(session["id"], after_sequence=snapshot["latestSequence"])
            if replay["events"]:
                raise RuntimeError("An empty session unexpectedly contains runtime work")
            try:
                client.replay(session["id"], after_sequence=snapshot["latestSequence"] + 100)
            except CursorError:
                report["cursor_conflict_checked"] = True
            else:
                raise RuntimeError("Ahead cursor was not rejected")
            try:
                client.get_run(session["id"], "run_nonexistent")
            except HTTPError as error:
                if error.status != 404:
                    raise
                report["missing_run_checked"] = True
            else:
                raise RuntimeError("Missing run was not rejected")
            report.update(status="passed", session_created=True, snapshot_checked=True, replay_checked=True)
        except Exception as error:
            report["error"] = redact(f"{type(error).__name__}: {error}")[:1500]
        finally:
            if proc:
                kill_tree(proc)
                proc.wait(timeout=10)
                proc.stdout.close()
                proc.stderr.close()
    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), "utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
