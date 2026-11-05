"""Tests for student guidance (REQ-4.1 to REQ-4.3)."""

import pytest

from contribution_tool.guidance import build_guidance
from contribution_tool.report import Report, StudentResult


def student(name, role, counts, grade=100):
    return StudentResult(
        name=name,
        role=role,
        accounts=("x",),
        methods=(),
        counts=counts,
        score=0.0,
        grade=grade,
    )


def guidance_for(*students):
    report = Report(students=list(students), targets={}, unlinked=[], warnings=[])
    return build_guidance(report)


THREE_BACK = (
    student("Test Öğrenci Bir", "Back", {"pr_merged": 1, "reviews": 4}),
    student("Test Öğrenci İki", "Back", {"pr_merged": 2, "reviews": 4}),
    student("Test Öğrenci Üç", "Back", {"pr_merged": 4, "reviews": 4}),
)


# REQ-4.1 — Each metric as a ratio of the role median


def test_ratio_to_role_median():
    guidance = guidance_for(*THREE_BACK)
    assert guidance["Test Öğrenci Bir"].ratios["pr_merged"] == 0.5
    assert guidance["Test Öğrenci Üç"].ratios["pr_merged"] == 2.0


def test_roles_are_compared_separately():
    tester = student("Test Öğrenci Dört", "Testçi", {"bugs_reported": 3})
    guidance = guidance_for(*THREE_BACK, tester)
    assert guidance["Test Öğrenci Dört"].ratios["bugs_reported"] == 1.0


# REQ-4.2 — Metrics that do not matter for the role, or nobody in the role has, are blank


def test_metric_with_low_weight_for_the_role_is_not_compared():
    # review comments weigh 0.5 for Back, below the threshold of 1
    guidance = guidance_for(*THREE_BACK)
    assert guidance["Test Öğrenci Bir"].ratios["review_comments"] is None


def test_metric_with_zero_role_median_is_not_compared():
    guidance = guidance_for(*THREE_BACK)
    assert guidance["Test Öğrenci Bir"].ratios["bugs_fixed"] is None


@pytest.mark.parametrize(("threshold", "expected"), [(0.5, 0.0), (1.0, None)])
def test_threshold_decides_which_metrics_are_compared(threshold, expected):
    students = [
        student("Test Öğrenci Bir", "Back", {"review_comments": 0}),
        student("Test Öğrenci İki", "Back", {"review_comments": 2}),
        student("Test Öğrenci Üç", "Back", {"review_comments": 2}),
    ]
    report = Report(students=students, targets={}, unlinked=[], warnings=[])
    guidance = build_guidance(report, threshold=threshold)
    assert guidance["Test Öğrenci Bir"].ratios["review_comments"] == expected


# REQ-4.3 — The weakest important metric as one sentence


def test_focus_names_the_weakest_metric_with_count_and_median():
    focus = guidance_for(*THREE_BACK)["Test Öğrenci Bir"].focus
    assert focus == "Pull requests merged: 1 (role median 2)"


def test_focus_when_at_or_above_median_everywhere():
    focus = guidance_for(*THREE_BACK)["Test Öğrenci Üç"].focus
    assert focus == "At or above the role median in every important area"


def test_focus_when_nothing_can_be_compared():
    alone = student("Test Öğrenci Bir", "Front", {})
    assert guidance_for(alone)["Test Öğrenci Bir"].focus.startswith("No comparison possible")


def test_unmatched_student_gets_no_guidance():
    unmatched = student("Test Öğrenci Beş", "Back", {}, grade=None)
    assert "Test Öğrenci Beş" not in guidance_for(*THREE_BACK, unmatched)


def test_unmatched_student_does_not_change_the_median():
    unmatched = student("Test Öğrenci Beş", "Back", {}, grade=None)
    guidance = guidance_for(*THREE_BACK, unmatched)
    assert guidance["Test Öğrenci Bir"].ratios["pr_merged"] == 0.5
