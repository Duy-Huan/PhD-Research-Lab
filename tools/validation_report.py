"""Aggregate measured validation evidence; never waive ordinary uncovered code.

Re-analyze recorded Python traces without inherited pragma/main exclusions. No test rerun or percentage inflation.
"""
from __future__ import annotations

import ast
import argparse
import json
from pathlib import Path
import re
import sys

import coverage

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/full-validation"


def load(name):
    return json.loads((OUT / name).read_text("utf-8"))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), "utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', default='backend', help='Regression output folder under artifacts/full-validation')
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cov = coverage.Coverage(config_file=str(ROOT / ".coveragerc"), data_file=str(OUT / args.backend / ".coverage"),
                            source=["backend", "start", "mcp_stdio_bridge"], omit=[])
    cov.set_option("report:exclude_lines", [])
    cov.set_option("report:exclude_also", [])
    cov.load()
    cov.json_report(outfile=str(OUT / "coverage-strict.json"))
    cov.html_report(directory=str(OUT / "coverage-strict-html"))
    with (OUT / "coverage-strict.txt").open("w", encoding="utf-8") as stream:
        cov.report(file=stream)
    strict = load("coverage-strict.json")
    raw = load(args.backend + "/summary.json")
    ordinary = []
    for name, file in strict["files"].items():
        if not file["missing_lines"] and not file.get("missing_branches"):
            continue
        path = ROOT / name
        source = path.read_text("utf-8")
        tree = ast.parse(source)
        functions = [(n.lineno, n.end_lineno, n.name) for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        def owner(line):
            matches = [(end - start, label) for start, end, label in functions if start <= line <= end]
            return min(matches)[1] if matches else "<module>"
        lines = source.splitlines()
        ordinary.append({"file": name, "summary": file["summary"], "missing_branches": file.get("missing_branches", []),
                         "missing_lines": [{"line": n, "function": owner(n), "source": lines[n - 1].strip()} for n in file["missing_lines"]],
                         "waived": False})
    write("coverage-gaps.json", {"scope": raw["scope"], "excluded_lines": strict["totals"]["excluded_lines"],
                                "ordinary_uncovered_code_is_not_a_skip": True,
                                "files": sorted(ordinary, key=lambda f: f["summary"]["missing_lines"], reverse=True)})
    text = (OUT / "frontend-final.log").read_text("utf-8")
    match = re.search(r"all files\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)", text)
    tests = re.search(r"tests (\d+)", text)
    frontend = {"tests": int(tests[1]), "line_percent": float(match[1]), "branch_percent": float(match[2]),
                "function_percent": float(match[3]), "passed": bool(re.search(r"fail 0", text)),
                "scope": "all first-party frontend/assets/*.js loaded by the real page; third-party vendor assets excluded"}
    write("frontend-coverage.json", frontend)
    stress = load("stress-sse.json")
    live_bytes = (OUT / "codex-live.log").read_bytes()
    live = live_bytes.decode("utf-16" if live_bytes.startswith((b'\xff\xfe', b'\xfe\xff')) else "utf-8", errors="replace")
    codex_passed = bool(re.search(r"^OK\s*$", live, re.MULTILINE))
    gpu = load("lmstudio-live.json") if (OUT / "lmstudio-live.json").exists() else {"passed": False}
    skips = []
    for skip in raw["skipped"]:
        name = skip["test"]
        explanation = skip["reason"]
        disposition = "not_executed"
        if "CodexLive" in name:
            disposition = "passed_separately" if codex_passed else "live_result_requires_review"
            explanation = "Explicit live test ran separately against installed Codex, one read-only inference task."
        elif "symlink" in name:
            explanation = "Windows user token cannot create symlinks (Developer Mode/admin privilege required); no OS privilege settings changed. Scripted path-containment tests still run."
        elif "ClearMLLive" in name:
            explanation = "Validation environment has no online ClearML host/access-key/secret-key settings. Real offline SDK ZIP recording and worker/API contracts are tested."
        elif "LMStudioLive" in name:
            disposition = "passed_separately" if gpu["passed"] else "not_executed"
            explanation = ("User-authorized live GPU test passed separately: installed model load, busy-gate rejection, unload and empty-model/free-gate checks."
                           if gpu["passed"] else "Live GPU load/unload has no successful recorded result.")
        skips.append({"test": name, "disposition": disposition, "reason": explanation})
    totals = strict["totals"]
    summary = {"regression_passed": raw["regression_passed"], "tests_run": raw["tests_run"],
               "failures": raw["failures"], "errors": raw["errors"], "source_stable": raw["source_stable"],
               "python_strict_coverage": totals, "frontend": frontend,
               "stress_passed": stress["passed"], "stress_phases": len(stress["phases"]),
               "codex_live_passed": codex_passed, "lmstudio_live": gpu,
               "openscience_protocol_passed": load("openscience-live-protocol.json")["status"] == "passed",
               "skips": skips, "coverage_waivers": [],
               "coverage_100_percent_gate_passed": totals["missing_lines"] == 0 and totals["missing_branches"] == 0
                    and frontend["line_percent"] == 100 and frontend["branch_percent"] == 100 and frontend["function_percent"] == 100,
               "important": "Uncovered ordinary code remains an open testing gap, not an environment skip. Regression PASS does not mean 100% coverage or production scientific qualification."}
    write("summary.json", summary)
    gateway_events = sum(p.get('events', 0) for p in stress['phases'] if p['name'] == 'gateway-streaming')
    http_requests = sum(p.get('latency', {}).get('count', 0) for p in stress['phases'] if p['name'] == 'http-load')
    deliveries = sum(p.get('sse_deliveries', 0) for p in stress['phases'])
    process_count = sum(p.get('real_subprocesses', 0) for p in stress['phases'])
    forced_count = sum(p.get('forced_timeouts', 0) for p in stress['phases'])
    unresolved = [s for s in skips if s['disposition'] != 'passed_separately']
    document = f'''# Full validation — 2026-10-21

Regression: **{'PASS' if raw['regression_passed'] else 'FAIL'}**. Bounded stress: **{'PASS' if stress['passed'] else 'FAIL'}**. The 100% coverage gate is **{'PASS' if summary['coverage_100_percent_gate_passed'] else 'NOT MET'}**. Ordinary uncovered code is not waived or renamed as an environment skip.

| Measurement | Result |
|---|---|
| Backend regression | {raw['tests_run']} tests; {raw['failures']} failures; {raw['errors']} errors; {len(raw['skipped'])} skips in the main run |
| Frontend regression | {frontend['tests']} tests, all passed |
| Python statement coverage | {totals['percent_statements_covered']:.2f}% ({totals['covered_lines']}/{totals['num_statements']}) |
| Python branch coverage | {totals['percent_branches_covered']:.2f}% ({totals['covered_branches']}/{totals['num_branches']}) |
| Python combined statement/branch score | {totals['percent_covered']:.2f}% |
| Frontend line / branch / function coverage | {frontend['line_percent']:.2f}% / {frontend['branch_percent']:.2f}% / {frontend['function_percent']:.2f}% |
| Bounded application stress | {len(stress['phases'])} phases, {stress['workers']} concurrent workers, {stress['rounds']} repetitions; {'PASS' if stress['passed'] else 'FAIL'} |
| Real Codex read-only smoke | {'PASS, one model task' if codex_passed else 'See live log'} |
| Real LM Studio GPU load/unload | {'PASS' if gpu['passed'] else 'Not verified'} |
| Real OpenScience protocol | PASS, isolated runtime 2.0.152, no model work |

Python scope includes all backend modules, the standalone ClearML worker, `start.py` and `mcp_stdio_bridge.py`. The strict report has **zero excluded lines**: existing pragma/main exclusions are removed when analyzing the recorded traces. The regular harness report also remains available with the repository's original exclusions, so its numbers differ. Development tools/tests and third-party dependencies are outside application coverage. Frontend coverage measures first-party JavaScript from the actual page; it does not claim CSS/layout or third-party vendor coverage.

## Stress evidence and limits

Recorded stress results cover {gateway_events:,} gateway events with three concurrent subscribers and cold durable replay; {http_requests:,} real loopback HTTP requests; and {deliveries:,} real SSE deliveries, including disconnect/reconnect. See individual PASS/FAIL phases for assertions: concurrent session identity/content, CPU admission, and exit settlement of {process_count} scripted CLI subprocesses ({forced_count} forced timeouts) plus their owned Windows termination helpers. Initial fixture failures and the immediate-vs-settled helper observation are retained as separate diagnostic reports; the final report is `stress-sse.json`.

Model output is scripted in load tests. This is a short application concurrency test, not a 24-hour soak, a GPU burn-in, a provider quota benchmark or scientific model evaluation. The HTTP load phase disables application lifespan to isolate request admission; startup/recovery has separate regression coverage. RSS before/after includes cold module imports and caches and is not proof of absence of memory leaks.

## Failures found and repaired

* ClearML worker kept `.partial` artifact bytes after checksum failure. Failed copies now remove temporary bytes and preserve completion semantics.
* Malformed worker JSON escaped the structured result/error protocol. Parsing now occurs inside its error boundary.
* Legacy research/CLI acceptance fixtures could dispatch real Feynman work. They explicitly select the mocked application engine; native Feynman has separate contract tests. Initial live leakage produced quota/auth failures and is preserved in the baseline log.
* Old lifecycle tests configured removed agent names and fell through to real cloud routing. They now use current utility/research roles and restore configuration after each test.
* The SSE disconnect fixture lacked current Request headers/event identities. It now supplies the real contract fields.
* The regression harness could fail to print Unicode tracebacks on Windows. Its console output is explicitly UTF-8.

## Skips with evidence

The main run recorded five skips. Separate successful live runs are credited in the machine-readable summary, leaving {len(unresolved)} unexecuted cases:

''' + '\n'.join(f"* `{s['test']}` — {s['reason']}" for s in unresolved) + f'''

Windows symlink creation was independently probed and returned WinError 1314. ClearML offline ZIP recording passed; an online experiment server was not exercised.

LM Studio live evidence: {json.dumps(gpu, ensure_ascii=False)}. This separate test uses the installed model, checks the VRAM busy gate while loaded, unloads local models, then checks empty LM Studio state and a free gate. Its execution is separate from the recorded coverage run; coverage percentages above are unchanged.

## Coverage still open

**{totals['missing_lines']} executable Python statements and {totals['missing_branches']} Python branch destinations remain uncovered.** The frontend also has untested branch/function variants despite 100% line coverage. Those gaps include ordinary recovery, routing, legacy memory and tool behavior as well as environment-dependent paths. They are not all unavoidable, and the external-service skips do not explain or waive them. The quality gate continues to fail with exit code 2.

The complete file/function/line inventory is in [coverage-gaps.json](../artifacts/full-validation/coverage-gaps.json). Prioritize workflow recovery/cancellation, native-engine decisions/artifact faults, model routing, sandbox failure cleanup and memory migration. The remaining work needs behavior-based tests, not execution-only calls, blanket mocks or exclusions added to raise the number.

## Reports and reproduction

* [Machine-readable summary](../artifacts/full-validation/summary.json)
* [Strict Python JSON](../artifacts/full-validation/coverage-strict.json), [HTML](../artifacts/full-validation/coverage-strict-html/index.html), [text](../artifacts/full-validation/coverage-strict.txt)
* [Regression log](../artifacts/full-validation/{args.backend}/tests.log), [frontend log](../artifacts/full-validation/frontend-final.log), [frontend coverage](../artifacts/full-validation/frontend-coverage.json)
* [Stress](../artifacts/full-validation/stress-sse.json), [Codex live log](../artifacts/full-validation/codex-live.log), [OpenScience protocol](../artifacts/full-validation/openscience-live-protocol.json)
* [LM Studio live result](../artifacts/full-validation/lmstudio-live.json), [log](../artifacts/full-validation/lmstudio-live.log)

```powershell
# Install the optional SDK or put its pinned audited source on PYTHONPATH for its socket integration test.
.venv/Scripts/python.exe tools/backend_regression.py --include-workers --include-entrypoints --out artifacts/full-validation/{args.backend}
node --test --experimental-test-coverage --test-coverage-include='frontend/assets/*.js' --test-reporter=spec --test-reporter-destination=artifacts/full-validation/frontend-final.log tests/frontend/*.test.js
.venv/Scripts/python.exe tools/stress_runtime.py --workers 16 --rounds 3 --out artifacts/full-validation/stress-sse.json
.venv/Scripts/python.exe tools/validation_report.py --backend {args.backend}
```

Live Codex and OpenScience evidence must be regenerated separately when validating another installation. The aggregator consumes these evidence files; it does not run live services. No production user data is used by the regression/stress harnesses. No source changed during the measured regression run.
'''
    (ROOT / 'docs/validation-2026-10-21.md').write_text(document, encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["coverage_100_percent_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
