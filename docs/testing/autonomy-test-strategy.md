# L1–L4 test strategy, 2026-10-24

This work applies the repository's three production QA master prompts and Engineering Principles. The user's explicit authorization permits actual LM Studio Qwen 3.5 9B inference; every test still uses disposable researcher state and no paid fallback. Local instructions that prohibit default real-model tests do not override that authorization.

## References and limits

| Reference | Applied practice | Evidence / limit |
|---|---|---|
| [AutoResearch AI](https://arxiv.org/html/2605.23204v1), sections 1, 3, 4 | Human control/verification choices, evidence, rejection and accountable closure | Typed policies and pending scientific review; does not demonstrate L3/L4 scientific autonomy |
| [ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html) public product-quality outline | Reliability, efficiency, security, usability | Measured fault, stress, browser and regression cases; no ISO certification claim |
| [ISO/IEC/IEEE 29119 overview](https://standards.ieee.org/ieee/29119-1/10779/) | Traceable requirements, cases, incidents and reports | Per-case results, retained failed runs, raw evidence and this strategy; full licensed standard not independently audited |
| [OWASP ASVS 5.0](https://asvs.owasp.org/) | Scoped authorization, strict validation, unsafe input and data integrity | Plan/result digests, cross-topic denial, capability checks and XML entity rejection; no full ASVS level attestation |
| [NIST SP 800-218 SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) | Reproduce defects, repair causes, scan dependencies, retain source identity | Before/after evidence and source hashes; not a certification |
| [WCAG 2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/) | Labels, keyboard controls, status/error feedback, viewport reflow | React interaction tests and real Edge desktop/mobile screenshots; not a full accessibility conformance audit |

## Harness procedure

1. Capture commit, source hashes, installed model/runtime and actual production-tree content hashes. Set a unique `PHDLAB_DATA_DIR` **before** backend imports.
2. Write failing regressions for a reproducible defect. Keep faults separate from real-model acceptance, and never substitute model output.
3. Exercise production services and actual loopback HTTP with the normal FastAPI lifespan. The new harness instruments real transport destinations and denies non-loopback socket connections; it never supplies inference responses. Browser requests are also constrained to the local application.
4. Approve exact test plans and protocols with clearly labelled simulated human decisions. Test that these decisions cannot be inferred from source/model text. Verify result reviews with plan and result hashes.
5. Run four concurrent, independent workflows over three repeats. For L4's CPU experiment path, use two separately approved snapshots and fresh Python worker processes, then independently recompute metrics and verify reproduction. Preserve raw observations and reports in ZIP evidence.
6. Test rejection, stale results, pause/resume, capability restrictions, cancellation, contention before admission, six-workflow fairness, project switches, and recovery from a fresh process. Validate corruption/tampering using negative oracles.
7. Run the complete nested offline regression discovery, all legacy live integration modules with selected Qwen, React tests with full source inventory, TypeScript/build, real Edge E2E, v6.0/v6.2/v6.3 research harnesses, dependency/static scans and 16-worker stress over three rounds.
8. Recompute production-tree hashes after shutdown. Record skipped/unavailable requirements explicitly. Treat a CI matrix declaration, a model list, synthetic literature or passing code tests as insufficient scientific/production certification.

## Required oracles

- Each admitted task runs at most once per attempt; duplicate tick callers cannot release another task's resource lease.
- Each workflow runs at most one task at once; the single process scheduler runs at most four ticks across projects. Local LLM and CPU slot limits remain authoritative.
- Unreviewed L1/L2 results stop continuation. Rejection cancels only that workflow. L3 requires final human review. L4 checks actual bytes and independently reproduced numerical evidence, leaving scientific review pending.
- Scope, provider/model, budget and deadline never expand during dispatch. Unknown token/cost usage remains unknown.
- Actual browser checks must inspect panel bounds and screenshots, not merely document overflow. A clipped panel can still have zero document overflow.
- Global code coverage, changed-file coverage, a finite branch/requirement matrix, model factuality and scientific autonomy are separate measurements. The user's 100% global target remains an unsatisfied gate whenever any production code/branch or required journey is unverified.

## Reproduction

```powershell
.venv\Scripts\python -B tools/backend_quality_gate.py --profile full --i-understand-full-suite --output-dir artifacts/autonomy-qa/backend-complete-source
cd frontend
npm run build
npm run test:coverage
cd ..
.venv\Scripts\python -B tools/autonomy_harness.py --model qwen/qwen3.5-9b --rounds 3 --browser --output artifacts/autonomy-qa/live
.venv\Scripts\python -B tools/run_legacy_live.py
.venv\Scripts\python -B tools/stress_runtime.py --workers 16 --rounds 3 --out artifacts/autonomy-qa/stress.json
.venv\Scripts\python -B tools/static_quality.py
```

`tools/live_quality_gate.py --profile all` orchestrates the principal suites and produces a conservative release decision. Its exit code remains nonzero when mandatory qualification is incomplete. The backend runner's exit code separately represents test execution; consult its per-gate report for release assessment. Run `tools/research_harness.py --stage 6.0`, `6.2`, `6.3` with distinct `--output` folders and verify their exports with `tools/verify_v6_harness.py`.

On this Windows host the same-version pure-Python SQLAlchemy install used `DISABLE_SQLALCHEMY_CEXT=1` plus `pip install --force-reinstall --no-deps --no-binary=SQLAlchemy SQLAlchemy==2.1.5`, following [SQLAlchemy's documented build option](https://docs.sqlalchemy.org/en/20/intro.html). No security-policy changes were made. Browser automation uses installed Edge; set `PHDLAB_BROWSER` for another installed executable. Do not run these tools inside the process of an already-imported production backend.
