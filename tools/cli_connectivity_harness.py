"""Opt-in real CLI probes in isolated data; never substitutes a fake provider."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--codex-model", default="")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.environ["PHDLAB_DATA_DIR"] = tempfile.mkdtemp(prefix="phdlab-cli-probe-")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.core.telemetry import redact
    from backend.providers.cli import CONNECTORS

    def probe(case):
        pid, model = case
        key = pid + ("-" + model if model else "-default")
        start = time.monotonic()
        record = {"provider": pid, "model": model or "vendor-default", "real_cli": True,
                  "health": CONNECTORS[pid].health(True), "events": []}
        try:
            for event in CONNECTORS[pid].stream_message(
                "Reply with the single word OK. Do not use tools, read files, or modify anything.",
                {"profile": "review", "model": model, "timeout_s": args.timeout},
            ):
                record["events"].append(json.loads(redact(json.dumps(event))))
        except Exception as exc:  # noqa: BLE001 - record real provider failures without aborting other probes
            record["exception"] = redact(str(exc))[:1500]
        record["elapsed_s"] = round(time.monotonic() - start, 3)
        record['health_after'] = CONNECTORS[pid].health()
        record["answer"] = "".join(e.get("text", "") for e in record["events"] if e["type"] == "text_delta")
        record["passed"] = bool(record["answer"].strip()) and not record.get("exception") and not any(
            e["type"] == "error" or (e["type"] == "request_completed" and e.get("exit_code", 0) != 0)
            for e in record["events"])
        (out / (key + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps({k: record[k] for k in ("provider", "model", "passed", "answer", "elapsed_s")}), flush=True)
        return record

    cases = [("codex", args.codex_model), ("claude_code", ""), ("antigravity", ""), ("gemini_cli", "")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(probe, cases))
    # An explicit stale-model error is preserved; the vendor default is a separate diagnostic.
    if args.codex_model and not results[0]["passed"]:
        results.append(probe(("codex", "")))
    (out / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
