"""Role-based scoring (REQ-3.2 to REQ-3.7)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from contribution_tool.matching import normalize_name

OTHER = "Diğer"
ROLES = ("Product Owner", "Scrum Master", "Back", "Front", "Testçi", OTHER)

ROLE_ALIASES = {
    "Product Owner": {"po", "product owner", "urun sahibi"},
    "Scrum Master": {"sm", "sc", "scrum master", "scrum"},
    "Back": {"back", "backend", "back-end", "dev", "developer", "gelistirici"},
    "Front": {"front", "frontend", "front-end"},
    "Testçi": {"testci", "test", "tester", "qa"},
}

METRICS = (
    "pr_opened",
    "pr_merged",
    "reviews",
    "review_comments",
    "discussion_posts",
    "stories_written",
    "stories_done",
    "tasks_closed",
    "bugs_reported",
    "bugs_fixed",
)

# fmt: off
#                   PO   SM   Back Front Test Diğer
_WEIGHT_TABLE = {
    "pr_opened":        (0.5, 0.5, 1.0, 1.0, 1.0, 1.0),
    "pr_merged":        (1.0, 1.0, 3.0, 3.0, 2.0, 3.0),
    "reviews":          (1.0, 2.0, 2.0, 2.0, 2.0, 2.0),
    "review_comments":  (0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    "discussion_posts": (1.0, 2.0, 0.5, 0.5, 0.5, 0.5),
    "stories_written":  (3.0, 1.0, 0.5, 0.5, 1.0, 1.0),
    "stories_done":     (2.0, 1.0, 2.0, 2.0, 1.0, 2.0),
    "tasks_closed":     (0.5, 1.0, 1.0, 1.0, 1.0, 1.0),
    "bugs_reported":    (1.0, 0.5, 1.0, 1.0, 3.0, 2.0),
    "bugs_fixed":       (0.5, 0.5, 2.0, 2.0, 1.0, 1.0),
}
# fmt: on

DEFAULT_WEIGHTS = {
    role: {metric: _WEIGHT_TABLE[metric][i] for metric in METRICS} for i, role in enumerate(ROLES)
}

TARGET_FACTOR = Decimal("1.2")


def canonical_role(value: str) -> str:
    """Map a role written in the student list to one of ROLES (REQ-3.6)."""
    text = normalize_name(value)
    for role, aliases in ROLE_ALIASES.items():
        if text in aliases:
            return role
    return OTHER


def score(counts: Mapping[str, int], role: str, weights=DEFAULT_WEIGHTS) -> float:
    """Weighted sum of a student's counts with the weights of their role (REQ-3.2)."""
    role_weights = weights[role]
    return sum(counts.get(metric, 0) * role_weights[metric] for metric in METRICS)


def role_target(scores: Iterable[float]) -> float:
    """Median of the scores in one role multiplied by 1.2 (REQ-3.3)."""
    values = list(scores)
    if not values:
        raise ValueError("A role target needs at least one score")
    return float(Decimal(str(median(values))) * TARGET_FACTOR)


def grade(student_score: float, target: float) -> int:
    """Score as a percentage of the role target, rounded half up, at most 100 (REQ-3.4, 3.5)."""
    if target <= 0:
        return 0
    # Decimal avoids float errors such as 9.95 / 10 * 100 == 99.49999999999999
    ratio = Decimal(str(student_score)) / Decimal(str(target)) * 100
    return min(100, int(ratio.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def scoring_warnings(students: Iterable[tuple[str, str]]) -> list[str]:
    """Warnings for unknown roles (REQ-3.6) and roles with one student (REQ-3.7).

    students: (name, canonical role) pairs
    """
    pairs = list(students)
    warnings = [
        f"{name}: role is empty or unknown, scored as '{OTHER}'"
        for name, role in pairs
        if role == OTHER
    ]
    for role, count in Counter(role for _, role in pairs).items():
        if count == 1:
            warnings.append(
                f"Role '{role}' has only one student; the grade compares them only with themselves"
            )
    return warnings
