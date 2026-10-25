"""Deliberately defective acceptance fixture, isolated from production application code."""


def add(left: int, right: int) -> int:
    return left + right + 1
