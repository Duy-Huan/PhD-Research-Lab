"""Conservative release assessment: execution success and certification are separate facts."""


def assess(tests, coverage=None, minimum=100):
    if tests.get("failures", 0) or tests.get("errors", 0):
        return "FAIL"
    if not tests.get("total_run", 0) or tests.get("skipped", 0) or not coverage:
        return "BLOCKED"
    lines = coverage.get("num_statements", 0)
    branches = coverage.get("num_branches", 0)
    if not lines or not branches:
        return "BLOCKED"
    if coverage.get("covered_lines", 0) * 100 < lines * minimum or coverage.get("covered_branches", 0) * 100 < branches * minimum:
        return "FAIL"
    return "CONDITIONAL"  # security/platform/manual release signoff require their own evidence
