from __future__ import annotations

from collections.abc import Iterable


def _non_empty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Iterable):
        return len(list(value)) > 0
    return True


def score_value(value: object, source_count: int = 1, conflict: bool = False, derived: bool = False) -> float:
    if not _non_empty(value):
        return 0.0
    score = 0.7
    if source_count > 1:
        score += 0.15
    if derived:
        score -= 0.1
    if conflict:
        score -= 0.25
    return max(0.0, min(1.0, round(score, 2)))

