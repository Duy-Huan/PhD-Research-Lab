"""Owner policy:100% required regressions; coverage is an informational measurement."""


def assess(tests, coverage=None, minimum=None):
    """Assess execution; legacy coverage arguments carry no threshold semantics.

    CONDITIONAL means complete software regression, not scientific/release approval.
    """
    keys = ('total_run', 'passed', 'failures', 'errors', 'skipped', 'not_run', 'blocked', 'unverified')
    counts = {key: tests.get(key, 0) for key in keys}
    if any(type(value) is not int or value < 0 for value in counts.values()):
        return 'BLOCKED'
    if counts['failures'] or counts['errors']:
        return 'FAIL'
    if (not counts['total_run'] or counts['passed'] != counts['total_run']
            or any(counts[key] for key in ('skipped', 'not_run', 'blocked', 'unverified'))):
        return 'BLOCKED'
    return 'CONDITIONAL'
