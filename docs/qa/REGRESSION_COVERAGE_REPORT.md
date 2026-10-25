# Regression and production coverage:6.5.6

Same-suite policy, environment and source denominators: [measured comparison](MAIN_CANDIDATE_COMPARISON.md). No test/exclusion/threshold was weakened. Raw PASS counts from different source capabilities do not rank branches.

| Production metric | Main | Candidate |
|---|---:|---:|
| Backend lines |21808/24306|23833/26528|
| Backend branches |6649/8132|7120/8808|
| Backend combined coverage |87.73%|87.60%|
| Frontend lines |UNAVAILABLE: collection errors|2445/3820=64.00%|
| Frontend branches |UNAVAILABLE|2611/4125=63.29%|
| Frontend functions |UNAVAILABLE|733/1467=49.96%|
| Frontend statements |UNAVAILABLE|2574/4117=62.52%|

Backend and frontend measures are separate. Main's missing frontend measurement is not0% and cannot be numerically ranked. Changed production denominators explain why combined coverage is not a direct correctness ranking.

Candidate gaps:2695backend lines/1688branches,1375frontend lines/1514branches,734frontend functions and1543statements remain uncovered. [Machine-readable gap priority](COVERAGE_GAPS_6.5.6.json) names current files, including API research/system, CLI repl, agent runs/missions. Add meaningful behavior/failure assertions; never execute unasserted paths simply to inflate a number.

Permanent regression additions retain the delayed metrics-publication oracle, exact release executable permissions, CI install ordering/fail accounting, context completeness, CLI/provider isolation, source evidence identity and local repair trust/state. UI-3D-LOCALE-001 remains NOT_IMPLEMENTED; the actual screenshot exposes why27browser PASS does not cover every localization requirement. No controlled human-approved visual baseline or hardware GPU qualification is claimed.

Eight selected mandatory skips and separate legacy/live inventories remain unqualified. PR/full gates preserve100%/complete-case enforcement; local feature checks are development feedback, not release acceptance. Full/live/AI-UAT gates must all pass before protected promotion.
