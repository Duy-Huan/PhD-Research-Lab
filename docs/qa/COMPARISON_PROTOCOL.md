# Same-suite comparison protocol

Main preview is untrusted. Compare production source, not absolute numbers of successful tests from different historical suites.

Executed6.5.6 comparison: [measured report](MAIN_CANDIDATE_COMPARISON.md). Both subjects retain mandatory typecheck/build outcomes and also run identical Vite-only diagnostic transpilation/postbuild before browser execution. Diagnostic success cannot change a failed mandatory build into PASS. Evidence-backed source review is labeled separately from automated cases; additional visual defects remain OPEN even when the fixed critical groups pass.

Use fresh isolated main and candidate checkouts. Preserve original branch commits and hash production backend, frontend/src and CLI inputs before/after instrumentation. Apply one frozen development verification bundle (tests, frontend/e2e, verification driver, contract/evidence inputs and evaluation configuration) to both. Record every overlay; never overwrite backend/frontend application source or silently present an instrumented checkout as a pristine historical runtime.

Run both serially on the same host using the same Python3.12 hash-locked environment, Node/dependency installation, Chromium binary, coverage policies and10 fixed software check groups in CRITICAL_SOFTWARE_CHECKS.json. Also run the same Python3.11 compilation compatibility probe on each. Use disposable data/profiles for every subject. Dependency/build instrumentation, source SHA/digest and environment hashes belong in the manifest. No passing cached result may replace execution.

Full backend strict coverage, frontend strict coverage/types/build and all non-model browser journeys (2D then actual3D) are separate commands in the existing harness. Live provider/research/AI-UAT remains a separate mandatory acceptance layer: no model quota is silently spent and unavailable/exhausted execution is BLOCKED. This offline comparison does not claim full scientific or all-provider acceptance.

Missing modules/removed APIs on old main can prevent new tests from loading. Preserve loader ERROR proxies and mark missing named critical cases NOT_RUN/BLOCKED; do not turn them into PASS, invent a per-case failure count, or automatically assign every loader error P1. Distinguish unsupported new features, proven legacy behavior defects, test-infrastructure incompatibility and unavailable services through raw evidence.

`scripts/compare_verification.py` refuses unequal recorded suite/environment/policy hashes. Critical rate uses the fixed groups as denominator and requires every named case in a group to PASS. A later duplicate PASS cannot erase FAIL/ERROR. Report backend line/branch counts and frontend line/branch/function/statement counts with their own source denominators; changed source scope is not proof of worse correctness. Do not rank branches by raw PASS totals.

P0/P1/P2 counts require reproduced, classified defect records. Zero confirmed findings in an incomplete audit does not mean zero bugs. Keep observed fixed/new/unclassified cases and mandatory NOT_RUN layers separate. Dev→qa and qa→main promotion require genuinely passing current-source mandatory checks and full/live acceptance; comparison results alone cannot authorize a merge or waive100% gates.
