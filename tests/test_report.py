"""Tests for combining all parts into one report (REQ-2.4, REQ-2.5, REQ-3.3)."""

from collections import Counter

from contribution_tool.github import GitHubData
from contribution_tool.report import build_report
from contribution_tool.students import Student
from contribution_tool.taiga import TaigaData


def github_data(counts=None, emails=None):
    data = GitHubData()
    for login, values in (counts or {}).items():
        data.counts[login] = Counter(values)
    for email, logins in (emails or {}).items():
        data.emails[email] = set(logins)
    return data


def taiga_data(counts=None, users=None):
    data = TaigaData()
    for user, values in (counts or {}).items():
        data.counts[user] = Counter(values)
    data.users.update(users or {})
    return data


def by_name(report):
    return {result.name: result for result in report.students}


# Counts from GitHub and Taiga are added up for each student


def test_counts_from_github_and_taiga_are_combined():
    student = Student(name="Test Öğrenci Bir", role="Back", emails=("bir@example.org",))
    github = github_data({"ogrencibir": {"pr_merged": 2}}, {"bir@example.org": ["ogrencibir"]})
    taiga = taiga_data({"bir": {"tasks_closed": 3}}, {"bir": "Test Öğrenci Bir"})
    result = build_report([student], github, taiga).students[0]
    assert result.counts == {"pr_merged": 2, "tasks_closed": 3}
    assert result.accounts == ("bir", "ogrencibir")


def test_role_is_read_from_the_student_list():
    student = Student(name="Test Öğrenci Bir", role="PO", usernames=("bir",))
    taiga = taiga_data({"bir": {"stories_written": 1}}, {"bir": ""})
    assert build_report([student], github_data(), taiga).students[0].role == "Product Owner"


# REQ-3.3 — Students are graded against the median of their own role


def test_median_student_of_a_role_gets_100():
    students = [
        Student(name="Test Öğrenci Bir", role="Back", usernames=("bir",)),
        Student(name="Test Öğrenci İki", role="Back", usernames=("iki",)),
        Student(name="Test Öğrenci Üç", role="Back", usernames=("uc",)),
    ]
    github = github_data({"bir": {"pr_merged": 1}, "iki": {"pr_merged": 2}, "uc": {"pr_merged": 4}})
    grades = {
        name: r.grade for name, r in by_name(build_report(students, github, taiga_data())).items()
    }
    assert grades == {"Test Öğrenci Bir": 50, "Test Öğrenci İki": 100, "Test Öğrenci Üç": 100}


def test_roles_are_graded_separately():
    students = [
        Student(name="Test Öğrenci Bir", role="Back", usernames=("bir",)),
        Student(name="Test Öğrenci İki", role="Testçi", usernames=("iki",)),
    ]
    github = github_data({"bir": {"pr_merged": 5}, "iki": {"pr_merged": 1}})
    report = build_report(students, github, taiga_data())
    assert [r.grade for r in report.students] == [100, 100]


# REQ-2.4 — Unmatched students are flagged, not given zero, and not in the median


def test_unmatched_student_has_no_grade_and_a_warning():
    student = Student(name="Test Öğrenci Üç", role="Back", emails=("uc@example.org",))
    report = build_report([student], github_data(), taiga_data())
    assert report.students[0].unmatched
    assert report.students[0].grade is None
    assert any("Test Öğrenci Üç" in w and "not matched" in w for w in report.warnings)


def test_unmatched_student_does_not_lower_the_median():
    students = [
        Student(name="Test Öğrenci Bir", role="Back", usernames=("bir",)),
        Student(name="Test Öğrenci İki", role="Back", usernames=("iki",)),
        Student(name="Test Öğrenci Üç", role="Back", emails=("uc@example.org",)),
    ]
    github = github_data({"bir": {"pr_merged": 2}, "iki": {"pr_merged": 4}})
    report = build_report(students, github, taiga_data())
    # scores 6 and 12: median 9; with the unmatched student's 0 it would be 6
    assert report.targets["Back"] == 9.0


# REQ-2.5 — Active accounts that belong to no student are listed


def test_unlinked_active_accounts_from_both_sources_are_listed():
    student = Student(name="Test Öğrenci Bir", role="Back", usernames=("bir",))
    github = github_data({"bir": {"pr_opened": 1}, "hoca": {"reviews": 5}})
    taiga = taiga_data(
        {"misafir": {"stories_written": 1}, "pasif": {}}, {"misafir": "", "pasif": ""}
    )
    assert build_report([student], github, taiga).unlinked == ["hoca", "misafir"]


# REQ-3.7 — Scoring warnings appear in the report


def test_single_student_role_warning_is_in_report():
    student = Student(name="Test Öğrenci Bir", role="Front", usernames=("bir",))
    report = build_report([student], github_data({"bir": {"pr_opened": 1}}), taiga_data())
    assert any("'Front'" in w for w in report.warnings)


# REQ-2.4 — Partially matched students get a warning
# Source: acceptance test, a student's Taiga account was not linked and no warning was shown


def test_student_without_taiga_account_gets_a_warning():
    student = Student(name="Test Öğrenci Bir", role="Back", usernames=("bir",))
    github = github_data({"bir": {"pr_merged": 1}})
    taiga = taiga_data({"ugurlu": {"tasks_closed": 4}}, {"ugurlu": "Farklı Ad"})
    report = build_report([student], github, taiga)
    assert any("Test Öğrenci Bir: no Taiga account" in w for w in report.warnings)
    assert "ugurlu" in report.unlinked


def test_student_without_github_account_gets_a_warning():
    student = Student(name="Test Öğrenci Bir", role="PO", usernames=("bir",))
    taiga = taiga_data({"bir": {"stories_written": 2}}, {"bir": ""})
    report = build_report([student], github_data({"baska": {"pr_opened": 1}}), taiga)
    assert any("Test Öğrenci Bir: no GitHub account" in w for w in report.warnings)


def test_no_partial_warning_when_linked_to_both():
    student = Student(name="Test Öğrenci Bir", role="Back", usernames=("bir",))
    github = github_data({"bir": {"pr_merged": 1}})
    taiga = taiga_data({"bir": {"tasks_closed": 1}}, {"bir": ""})
    report = build_report([student], github, taiga)
    assert not any("account found" in w for w in report.warnings)


def test_no_taiga_warning_when_no_taiga_data_is_given():
    student = Student(name="Test Öğrenci Bir", role="Back", usernames=("bir",))
    report = build_report([student], github_data({"bir": {"pr_merged": 1}}), taiga_data())
    assert not any("Taiga account" in w for w in report.warnings)


def test_unmatched_student_gets_only_the_unmatched_warning():
    student = Student(name="Test Öğrenci Üç", role="Back", emails=("uc@example.org",))
    taiga = taiga_data({"baska": {"tasks_closed": 1}}, {"baska": ""})
    report = build_report([student], github_data({"x": {"pr_opened": 1}}), taiga)
    student_warnings = [w for w in report.warnings if w.startswith("Test Öğrenci Üç")]
    assert student_warnings == ["Test Öğrenci Üç: not matched to any GitHub or Taiga account"]


# REQ-2.7 — Unused values in the student list appear as warnings


def test_unused_value_appears_as_warning_when_a_source_is_missing():
    student = Student(name="Test Öğrenci Bir", role="Testçi", usernames=("bir", "ayşe"))
    taiga = taiga_data({"ayseshn8": {"stories_accepted": 3}}, {"ayseshn8": "Ayşe"})
    report = build_report([student], github_data({"bir": {"pr_opened": 1}}), taiga)
    assert "Test Öğrenci Bir: 'ayşe' in the student list matched no account" in report.warnings


def test_no_unused_warning_when_linked_to_both_sources():
    # Acceptance test: every student had warnings for a display name and an e-mail not
    # used in commits, although they were linked to GitHub and Taiga anyway
    student = Student(
        name="Test Öğrenci Bir",
        role="Back",
        usernames=("bir", "test öğrenci bir"),
        emails=("bir@example.org",),
    )
    taiga = taiga_data({"t.bir": {"tasks_closed": 1}}, {"t.bir": "Test Öğrenci Bir"})
    report = build_report([student], github_data({"bir": {"pr_opened": 1}}), taiga)
    assert not any("matched no account" in w for w in report.warnings)


def test_no_unused_warning_when_every_value_matches():
    student = Student(name="Test Öğrenci Bir", role="Back", usernames=("bir",))
    report = build_report([student], github_data({"bir": {"pr_opened": 1}}), taiga_data())
    assert not any("matched no account" in w for w in report.warnings)
