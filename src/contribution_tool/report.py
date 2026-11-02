"""Combining matching, collection and scoring into one report (REQ-2.4, REQ-2.5, REQ-3)."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from contribution_tool.github import GitHubData
from contribution_tool.matching import match_students, unlinked_accounts
from contribution_tool.scoring import (
    DEFAULT_TARGET_FACTOR,
    canonical_role,
    grade,
    role_target,
    score,
    scoring_warnings,
)
from contribution_tool.students import Student
from contribution_tool.taiga import TaigaData


@dataclass(frozen=True)
class StudentResult:
    name: str
    role: str
    accounts: tuple[str, ...]
    methods: tuple[str, ...]
    counts: dict[str, int]
    score: float
    grade: int | None  # None when the student is not matched to any account (REQ-2.4)

    @property
    def unmatched(self) -> bool:
        return self.grade is None


@dataclass(frozen=True)
class Report:
    students: list[StudentResult]
    targets: dict[str, float]
    unlinked: list[str]
    warnings: list[str]


def build_report(
    students: Iterable[Student],
    github: GitHubData,
    taiga: TaigaData,
    factor: float = DEFAULT_TARGET_FACTOR,
) -> Report:
    """Match students, add up their counts, and grade them within their role."""
    matches = match_students(students, github.users, github.emails, taiga.users)

    rows = []
    for match in matches:
        counts: Counter = Counter()
        for account in match.github:
            counts.update(github.counts.get(account, {}))
        for account in match.taiga:
            counts.update(taiga.counts.get(account, {}))
        role = canonical_role(match.student.role)
        rows.append((match, role, dict(counts), score(counts, role)))

    # Unmatched students do not take part in the role median (REQ-3.3)
    scores_by_role = defaultdict(list)
    for match, role, _, student_score in rows:
        if not match.unmatched:
            scores_by_role[role].append(student_score)
    targets = {role: role_target(scores, factor) for role, scores in scores_by_role.items()}

    results = [
        StudentResult(
            name=match.student.name,
            role=role,
            accounts=tuple(sorted(match.github | match.taiga)),
            methods=match.methods,
            counts=counts,
            score=student_score,
            grade=None if match.unmatched else grade(student_score, targets[role]),
        )
        for match, role, counts, student_score in rows
    ]

    active_taiga = {user for user, c in taiga.counts.items() if sum(c.values()) > 0}
    warnings = scoring_warnings((r.name, r.role) for r in results if not r.unmatched)
    warnings += [
        f"{r.name}: not matched to any GitHub or Taiga account" for r in results if r.unmatched
    ]

    return Report(
        students=results,
        targets=targets,
        unlinked=unlinked_accounts(matches, github.users | active_taiga),
        warnings=warnings,
    )
