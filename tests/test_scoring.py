"""Tests for role-based scoring (REQ-3.2 to REQ-3.7)."""

import pytest

from contribution_tool.scoring import (
    DEFAULT_WEIGHTS,
    OTHER,
    canonical_role,
    grade,
    role_target,
    score,
    scoring_warnings,
)

# REQ-3.2 — Score is the weighted sum with the weights of the student's role


def test_score_uses_weights_of_the_role():
    counts = {"stories_written": 2, "pr_merged": 1}
    po = DEFAULT_WEIGHTS["Product Owner"]
    expected = 2 * po["stories_written"] + 1 * po["pr_merged"]
    assert score(counts, "Product Owner") == expected


def test_same_counts_give_different_scores_for_different_roles():
    counts = {"bugs_reported": 4}
    assert score(counts, "Testçi") > score(counts, "Back")


def test_missing_metrics_count_as_zero():
    assert score({}, "Back") == 0


# REQ-3.3 — Target is the median of the role times the target factor (default 1.0)


def test_target_with_one_score():
    assert role_target([10]) == 10


def test_target_with_odd_number_of_scores():
    assert role_target([2, 10, 30]) == 10


def test_target_with_even_number_of_scores():
    assert role_target([2, 8, 12, 30]) == 10


def test_target_without_scores_stops_with_error():
    with pytest.raises(ValueError):
        role_target([])


def test_median_student_gets_100_with_default_factor():
    scores = [2, 10, 30]
    assert grade(10, role_target(scores)) == 100


def test_target_factor_can_be_changed():
    assert role_target([10], factor=1.2) == 12


@pytest.mark.parametrize("factor", [0, -1])
def test_target_factor_must_be_positive(factor):
    with pytest.raises(ValueError):
        role_target([10], factor=factor)


# REQ-3.4 — Boundary values from the test plan (target = 10)


@pytest.mark.parametrize(
    ("student_score", "expected"),
    [
        (0, 0),  # lower bound
        (9.94, 99),  # just below the rounding boundary
        (9.95, 100),  # rounding boundary: 99.5 rounds up
        (10, 100),  # equal to target
        (15, 100),  # above target, capped at 100
    ],
)
def test_grade_boundary_values(student_score, expected):
    assert grade(student_score, 10) == expected


def test_grade_rounds_half_up_not_to_even():
    # Python's round() would give 98 here (round half to even)
    assert grade(9.85, 10) == 99


# REQ-3.5 — Decision table: student score zero? x everyone in role zero?


def test_zero_score_with_positive_target_gives_zero():
    assert grade(0, role_target([0, 5, 10])) == 0


def test_everyone_zero_gives_zero_for_everyone():
    target = role_target([0, 0, 0])
    assert [grade(s, target) for s in (0, 0, 0)] == [0, 0, 0]


def test_positive_score_with_positive_target_gives_positive_grade():
    assert grade(5, role_target([5, 10])) > 0


# REQ-3.6 — Role names are recognized; unknown or empty role becomes "Diğer"


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("PO", "Product Owner"),
        ("product owner", "Product Owner"),
        ("SC", "Scrum Master"),
        ("Dev", "Back"),
        ("Frontend", "Front"),
        ("TESTÇİ", "Testçi"),
        ("QA", "Testçi"),
        ("", OTHER),
        ("Analist", OTHER),
    ],
)
def test_canonical_role(written, expected):
    assert canonical_role(written) == expected


def test_unknown_role_produces_warning():
    warnings = scoring_warnings([("Test Öğrenci Bir", OTHER), ("Test Öğrenci İki", OTHER)])
    assert any("Test Öğrenci Bir" in w for w in warnings)


# REQ-3.7 — Role with a single student produces a warning


def test_single_student_role_produces_warning():
    students = [
        ("Test Öğrenci Bir", "Front"),
        ("Test Öğrenci İki", "Back"),
        ("Test Öğrenci Üç", "Back"),
    ]
    warnings = scoring_warnings(students)
    assert any("'Front'" in w for w in warnings)
    assert not any("'Back'" in w for w in warnings)


def test_no_warnings_when_roles_are_known_and_shared():
    students = [("Test Öğrenci Bir", "Back"), ("Test Öğrenci İki", "Back")]
    assert scoring_warnings(students) == []
