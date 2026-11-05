"""Guidance for students: where they stand compared with their role (REQ-4.1 to REQ-4.3)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from contribution_tool.report import Report
from contribution_tool.scoring import DEFAULT_WEIGHTS, METRICS

IMPORTANT_WEIGHT = 1.0

LABELS = {
    "pr_opened": "Pull requests opened",
    "pr_merged": "Pull requests merged",
    "reviews": "Code reviews",
    "review_comments": "Review comments",
    "discussion_posts": "Discussion posts",
    "stories_written": "User stories written",
    "stories_done": "User stories done",
    "tasks_closed": "Tasks closed",
    "bugs_reported": "Bugs reported",
    "bugs_fixed": "Bugs fixed",
    "stories_accepted": "Stories moved to Done",
    "taiga_comments": "Taiga comments",
}


@dataclass(frozen=True)
class Guidance:
    ratios: dict[str, float | None]  # count / role median; None when not compared
    focus: str


def build_guidance(
    report: Report, weights=DEFAULT_WEIGHTS, threshold: float = IMPORTANT_WEIGHT
) -> dict[str, Guidance]:
    """Guidance per student name; unmatched students get none."""
    matched = [r for r in report.students if not r.unmatched]
    counts_by_role = defaultdict(lambda: defaultdict(list))
    for r in matched:
        for metric in METRICS:
            counts_by_role[r.role][metric].append(r.counts.get(metric, 0))
    medians = {
        role: {metric: median(values) for metric, values in by_metric.items()}
        for role, by_metric in counts_by_role.items()
    }

    guidance = {}
    for r in matched:
        ratios = {}
        for metric in METRICS:
            role_median = medians[r.role][metric]
            # REQ-4.2: only metrics that matter for the role; no comparison with a zero median
            if weights[r.role][metric] < threshold or role_median == 0:
                ratios[metric] = None
            else:
                ratios[metric] = r.counts.get(metric, 0) / role_median
        guidance[r.name] = Guidance(ratios, _focus(r.counts, ratios, medians[r.role]))
    return guidance


def _focus(counts: dict[str, int], ratios: dict[str, float | None], medians) -> str:
    """REQ-4.3: the weakest important metric, with the student's count and the role median."""
    compared = {metric: ratio for metric, ratio in ratios.items() if ratio is not None}
    if not compared:
        return "No comparison possible: nobody in the role has these contributions yet"
    weakest = min(compared, key=compared.get)
    if compared[weakest] >= 1:
        return "At or above the role median in every important area"
    return f"{LABELS[weakest]}: {counts.get(weakest, 0)} (role median {medians[weakest]:g})"
