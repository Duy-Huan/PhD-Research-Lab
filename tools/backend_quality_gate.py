"""Backend Production Quality Gate Test Orchestrator.

Implements M1 & executes gates G0-G13 in compliance with:
- ISO/IEC 25010:2023 (Quality properties)
- ISO/IEC/IEEE 29119 (Test process & documentation)
- OWASP ASVS 5.0 (Security verification)
- NIST SP 800-218 (Secure software development framework)
- OWASP Top 10 for LLM Applications & Agentic AI

Strict safety:
- Always executes against an isolated disposable PHDLAB_DATA_DIR.
- Never accesses live researcher data, user papers, or production API keys.
- Denies paid external API calls by default via offline test fakes.
- Generates artifacts/backend-qa/report.json, unittest.log, coverage.json.
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "backend-qa"

SMOKE_MODULES = [
    "test_backend_quality_gate",
    "test_backend_faults_core",
    "test_backend_faults_api",
    "test_missions",
    "test_workstreams",
    "test_research_os",
    "test_guard",
    "test_firewall",
    "test_phdlab_native_engine",
]

CORE_MODULES = [
    "test_backend_quality_gate",
    "test_backend_faults_core",
    "test_backend_faults_api",
    "test_missions",
    "test_workstreams",
    "test_research_os",
    "test_guard",
    "test_firewall",
    "test_phdlab_native_engine",
    "test_api",
    "test_agent",
    "test_provider_faults",
    "test_provider_connectivity",
    "test_runtime_boundaries",
    "test_regression_boundaries",
    "test_regression_branches",
    "test_regression_isolation",
    "test_regression_integrity",
    "test_regression_retrieval",
    "test_regression_small_faults",
    "test_regression_system_faults",
    "test_memory_migration",
    "test_memory_v2",
    "test_memory_v33",
    "test_teams",
    "test_reasoning",
    "test_protocols",
    "test_governance",
    "test_harness_verification",
]

AUTONOMY_MODULES = ["test_autonomy", "test_workflow_worker", "test_qwen_local", "test_quality_evidence", "test_xml_search_security"]
SMOKE_MODULES += AUTONOMY_MODULES
CORE_MODULES += AUTONOMY_MODULES


def get_git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL, timeout=30)
        return out.strip()
    except Exception:
        return "unknown"


def get_git_dirty() -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL, timeout=30)
        return bool(out.strip())
    except Exception:
        return False


class QualityGateTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.test_cases_recorded = []
        self.subtests = []

    def startTest(self, test):
        super().startTest(test)
        self._test_start_time = time.perf_counter()
        target = os.environ.get('PHDLAB_VERIFY_PROGRESS')
        if target:
            path = Path(target)
            temporary = path.with_suffix('.partial-' + str(os.getpid()) + '-' + str(time.time_ns()))
            temporary.write_text(json.dumps({'test': test.id(), 'status': 'RUNNING',
                'completed_cases': len(self.test_cases_recorded), 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()}), 'utf-8')
            from backend.memory.store import replace_retry
            replace_retry(temporary, path)

    def addSuccess(self, test):
        super().addSuccess(test)
        duration = time.perf_counter() - getattr(self, "_test_start_time", time.perf_counter())
        self.test_cases_recorded.append({
            "id": test.id(),
            "status": "PASS",
            "duration": round(duration, 4),
            "details": None,
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        duration = time.perf_counter() - getattr(self, "_test_start_time", time.perf_counter())
        self.test_cases_recorded.append({
            "id": test.id(),
            "status": "FAIL",
            "duration": round(duration, 4),
            "details": self._exc_info_to_string(err, test),
        })

    def addError(self, test, err):
        super().addError(test, err)
        duration = time.perf_counter() - getattr(self, "_test_start_time", time.perf_counter())
        self.test_cases_recorded.append({
            "id": test.id(),
            "status": "ERROR",
            "duration": round(duration, 4),
            "details": self._exc_info_to_string(err, test),
        })

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        duration = time.perf_counter() - getattr(self, "_test_start_time", time.perf_counter())
        self.test_cases_recorded.append({
            "id": test.id(),
            "status": "SKIP",
            "duration": round(duration, 4),
            "details": reason,
        })

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.subtests.append({'parent': test.id(), 'id': subtest.id(), 'status': 'PASS' if err is None else 'FAIL' if issubclass(err[0], test.failureException) else 'ERROR',
                              'details': None if err is None else self._exc_info_to_string(err, subtest)})

    def stopTest(self, test):
        if not any(case['id'] == test.id() for case in self.test_cases_recorded):
            failed = [case for case in self.subtests if case['parent'] == test.id() and case['status'] in ('FAIL', 'ERROR')]
            self.test_cases_recorded.append({'id': test.id(), 'status': 'ERROR' if any(c['status'] == 'ERROR' for c in failed) else 'FAIL' if failed else 'UNVERIFIED',
                'duration': round(time.perf_counter() - self._test_start_time, 4),
                'details': '\n'.join(case['details'] for case in failed) or 'No success assertion outcome was recorded'})
        super().stopTest(test)


class TeeStream:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


def run_gate(
    profile: str = "smoke",
    coverage_enabled: bool = True,
    output_dir: Path | None = None,
    allow_full: bool = False,
    require_complete: bool = False,
    layer: str = 'software',
) -> int:
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if profile == "full" and not allow_full:
        print("ERROR: Full test profile requested without --i-understand-full-suite confirmation.")
        print("Running all 690+ tests takes several minutes. Pass --i-understand-full-suite to proceed.")
        return 2

    # 1. Setup isolated throwaway storage
    temp_data_dir = tempfile.mkdtemp(prefix="phdlab-gate-")
    os.environ["PHDLAB_DATA_DIR"] = temp_data_dir
    os.environ["PHDLAB_QA_OFFLINE"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["JUPYTER_DATA_DIR"] = os.path.join(temp_data_dir, "_jupyter")

    # Safety assertion against touching live data
    if (ROOT / "data").resolve() == Path(temp_data_dir).resolve():
        raise RuntimeError("CRITICAL ERROR: Quality gate pointing to live data directory!")

    # Set python path
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if str(ROOT / "tests") not in sys.path:
        sys.path.insert(0, str(ROOT / "tests"))

    from tools.qa_harness import source_hashes
    before_hashes = {k: v for k, v in source_hashes().items() if k.startswith('backend/')}
    start_time = datetime.datetime.now(datetime.timezone.utc)
    log_file_path = output_dir / "unittest.log"
    report_file_path = output_dir / "report.json"
    coverage_file_path = output_dir / "coverage.json"

    cov = None
    if coverage_enabled:
        try:
            import coverage
            cov = coverage.Coverage(
                config_file=str(ROOT / ".coveragerc") if (ROOT / ".coveragerc").exists() else True,
                branch=True,
                source=["backend", str(ROOT / 'tools' / 'hermes_runtime')],
                data_file=str(output_dir / ".coverage"),
            )
            cov.start()
        except Exception as e:
            print(f"Warning: Coverage collection could not start: {e}")
            cov = None

    # Begin tracing before application imports, including module-level declarations.
    import _env  # noqa: F401

    log_buffer = io.StringIO()
    tee_stream = TeeStream(sys.stderr, log_buffer)

    loader = unittest.defaultTestLoader
    from devtools.verification.layers import load_modules,EmptyTestModule
    if profile == "smoke":
        modules = [m for m in SMOKE_MODULES if (ROOT / "tests" / f"{m}.py").exists()]
        suite = load_modules(loader,modules)
    elif profile == "core":
        modules = [m for m in CORE_MODULES if (ROOT / "tests" / f"{m}.py").exists()]
        suite = load_modules(loader,modules)
    elif profile == "full":
        from devtools.verification.selection import select
        discovered=select(ROOT,[],'pr')
        suite=load_modules(loader,discovered['backend_tests'])
        for name in discovered['blocked_tests']:
            suite.addTest(EmptyTestModule(name+' (unpackaged test directory)'))
    else:
        suite = load_modules(loader,[profile])

    from devtools.verification.layers import partition
    suite, deferred_tests = partition(suite, layer)
    runner = unittest.TextTestRunner(
        stream=tee_stream,
        verbosity=2,
        resultclass=QualityGateTestResult,
    )

    t0 = time.perf_counter()
    import faulthandler
    with (output_dir / 'stall-stacks.log').open('w', encoding='utf-8') as stacks:
        faulthandler.dump_traceback_later(300, repeat=True, file=stacks)
        try: result = runner.run(suite)
        finally: faulthandler.cancel_dump_traceback_later()
    after_hashes = {k: v for k, v in source_hashes().items() if k.startswith('backend/')}
    source_stable = before_hashes == after_hashes
    elapsed = time.perf_counter() - t0
    end_time = datetime.datetime.now(datetime.timezone.utc)

    # Stop coverage
    coverage_summary = {}
    if cov is not None:
        try:
            cov.stop()
            cov.save()
            cov.json_report(outfile=str(coverage_file_path))
            with open(coverage_file_path, "r", encoding="utf-8") as cf:
                cov_data = json.load(cf)
                totals = cov_data.get("totals", {})
                coverage_summary = {
                    "percent_covered": round(totals.get("percent_covered", 0.0), 2),
                    "covered_lines": totals.get("covered_lines", 0),
                    "num_statements": totals.get("num_statements", 0),
                    "covered_branches": totals.get("covered_branches", 0),
                    "num_branches": totals.get("num_branches", 0),
                }
        except Exception as e:
            print(f"Warning: Coverage reporting failed: {e}")

    # Write unittest.log
    with open(log_file_path, "w", encoding="utf-8") as lf:
        lf.write(log_buffer.getvalue())

    # Build Quality Gate mappings
    # G0: Test integrity (no fails, no blocked mandatory)
    # G1: Data safety (verified isolated temp dir)
    # G2: Mission authority (state machine, approvals, digest, capabilities)
    # G3: Recovery (SQLite durable restart, crash recovery)
    # G4: Evidence (SHA-256 verification, metric validation, tampering catch)
    # G5: API contract (OpenAPI parity, negative tests, 422, unicode)
    # G6: Security (ASVS 5.0, injections, path traversal, no secret leak)
    # G7: Multi-provider (offline matrix, timeout, 429/5xx, disconnects)
    # G8: Resource (guard slots, GPU memory admission, process limits)
    # G9: Coverage (transparent branch + line measurement)
    # G10: Performance (baseline timing, zero timeouts)
    # G11: Observability (telemetry redaction, span tracking)
    # G12: Cross-platform (Windows & Linux compatibility)
    # G13: Integration (end-to-end mission-tool-evidence offline workflow)
    passed_all = result.wasSuccessful()
    gates = {
        "G0_Test_Integrity": "PASS" if passed_all else "FAIL",
        "G1_Data_Safety": "PASS" if os.environ["PHDLAB_DATA_DIR"] == temp_data_dir else "FAIL",
        "G2_Mission_Authority": "PASS" if passed_all else "FAIL",
        "G3_Recovery": "PASS" if passed_all else "FAIL",
        "G4_Evidence_Integrity": "PASS" if passed_all else "FAIL",
        "G5_API_Parity": "PASS" if passed_all else "FAIL",
        "G6_Security_ASVS": "PASS" if passed_all else "FAIL",
        "G7_Multi_Provider": "PASS" if passed_all else "FAIL",
        "G8_Resource_Guard": "PASS" if passed_all else "FAIL",
        "G9_Coverage": "INFORMATIONAL" if coverage_summary else "UNAVAILABLE",
        "G10_Performance": "PASS" if elapsed < 600 else "FAIL",
        "G11_Observability": "PASS" if passed_all else "FAIL",
        "G12_Cross_Platform": "BLOCKED",
        "G13_Offline_Integration": "PASS" if passed_all else "FAIL",
    }

    # Passing a selected test suite cannot establish unexecuted production/security gates.
    for name in ("G1_Data_Safety", "G3_Recovery", "G6_Security_ASVS", "G7_Multi_Provider", "G10_Performance", "G11_Observability"):
        gates[name] = "CONDITIONAL" if passed_all else "FAIL"
    if result.skipped:
        gates["G0_Test_Integrity"] = "BLOCKED"
    from tools.quality_evidence import assess
    decision = assess({'total_run': result.testsRun,
                       'passed': sum(c['status']=='PASS' for c in result.test_cases_recorded),
                       'unverified': sum(c['status']=='UNVERIFIED' for c in result.test_cases_recorded),
                       'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}, coverage_summary)
    if not source_stable and decision != 'FAIL':
        decision = 'BLOCKED'

    report = {
        "metadata": {
            "timestamp": start_time.isoformat(),
            "completion_time": end_time.isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "profile": profile,
            "git_commit": get_git_commit(),
            "git_dirty": get_git_dirty(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "data_dir_isolated": temp_data_dir,
            "release_scope": 'v' + sys.modules['backend.core.config'].APP_VERSION,
            "source_stable": source_stable,
            "test_layer": layer,
            "source_files_sha256": before_hashes,
        },
        "summary": {
            "total_run": result.testsRun,
            "passed": sum(case['status'] == 'PASS' for case in result.test_cases_recorded),
            "failures": sum(case['status'] == 'FAIL' for case in result.test_cases_recorded),
            "errors": sum(case['status'] == 'ERROR' for case in result.test_cases_recorded),
            "failure_events": len(result.failures),
            "error_events": len(result.errors),
            "skipped": len(result.skipped),
            "was_successful": passed_all,
            "overall_decision": decision,
        },
        "coverage": coverage_summary,
        "coverage_policy": {'mode':'INFORMATIONAL','percentage_gate':False},
        "deferred_tests": deferred_tests,
        "quality_gates": gates,
        "cases": getattr(result, "test_cases_recorded", []),
        "subtests": result.subtests,
        "limitations": ["Per-test success is scoped to executed cases; no blanket security or platform certification", "Required skipped/unexecuted regression cases block; coverage percentages are informational", "Declared live-provider cases are NOT_RUN in software and required at QA/main"],
    }

    with open(report_file_path, "w", encoding="utf-8") as rf:
        json.dump(report, rf, indent=2, ensure_ascii=False)

    # Cleanup temp directory
    try:
        shutil.rmtree(temp_data_dir, ignore_errors=True)
    except Exception:
        pass

    print("\n" + "=" * 60)
    print(f"Backend Quality Gate [{profile.upper()}]: {'PASS' if passed_all else 'FAIL'}")
    print(f"Release assessment: {decision}")
    print(f"Tests Run: {result.testsRun} | Passed: {report['summary']['passed']} | Failures: {len(result.failures)} | Errors: {len(result.errors)} | Skipped: {len(result.skipped)}")
    print(f"Duration: {elapsed:.2f}s")
    if coverage_summary:
        print(f"Coverage combined: {coverage_summary.get('percent_covered')}%; lines {coverage_summary.get('covered_lines')}/{coverage_summary.get('num_statements')}; branches {coverage_summary.get('covered_branches')}/{coverage_summary.get('num_branches')}")
    print(f"Report: {report_file_path}")
    print(f"Log: {log_file_path}")
    print("=" * 60)

    return 0 if passed_all and source_stable and (not require_complete or decision == 'CONDITIONAL') else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="PhD Research Lab Backend Quality Gate Orchestrator")
    parser.add_argument("--profile", choices=["smoke", "core", "full"], default="smoke", help="Execution profile")
    parser.add_argument("--no-coverage", action="store_true", help="Disable coverage instrumentation")
    parser.add_argument('--require-complete', action='store_true', help='Require every selected regression to execute and pass; coverage is informational')
    parser.add_argument('--layer', choices=['software','live','all'], default='software')
    parser.add_argument("--i-understand-full-suite", action="store_true", help="Confirm execution of the full test suite")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory to save report and logs")
    args = parser.parse_args()

    return run_gate(
        profile=args.profile,
        coverage_enabled=not args.no_coverage,
        output_dir=args.output_dir,
        allow_full=args.i_understand_full_suite,
        require_complete=args.require_complete,
        layer=args.layer,
    )


if __name__ == "__main__":
    raise SystemExit(main())
