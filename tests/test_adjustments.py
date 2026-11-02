"""Tests for instructor adjustments with a written reason (REQ-3.11)."""

from collections import Counter

import pytest

from contribution_tool.adjustments import Adjustment, load_adjustments
from contribution_tool.github import GitHubData
from contribution_tool.report import build_report
from contribution_tool.students import Student
from contribution_tool.taiga import TaigaData


def write_csv(tmp_path, text, encoding="utf-8"):
    path = tmp_path / "duzeltmeler.csv"
    path.write_text(text, encoding=encoding)
    return path


def report_for(adjustments, scores=(2, 4, 8)):
    """Three Back students; with factor 1.0 their grades are 50, 100 and 100."""
    names = ["Test Öğrenci Bir", "Test Öğrenci İki", "Test Öğrenci Üç"]
    students = [
        Student(name=name, role="Back", usernames=(f"u{i}",)) for i, name in enumerate(names)
    ]
    github = GitHubData()
    for i, points in enumerate(scores):
        github.counts[f"u{i}"] = Counter({"review_comments": points * 2})  # 0.5 points each
    by_name = {
        r.name: r for r in build_report(students, github, TaigaData(), 1.0, adjustments).students
    }
    return by_name


# Loading the adjustments file


def test_adjustments_are_loaded(tmp_path):
    path = write_csv(
        tmp_path, "ad_soyad,puan,gerekce\nTest Öğrenci Bir,+10,Backlog SM tarafından açıldı\n"
    )
    assert load_adjustments(path) == [
        Adjustment("Test Öğrenci Bir", 10, "Backlog SM tarafından açıldı")
    ]


def test_negative_points_are_loaded(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,puan,gerekce\nTest Öğrenci Bir,-5,Geç teslim\n")
    assert load_adjustments(path)[0].points == -5


def test_file_saved_by_excel_is_loaded(tmp_path):
    text = "ad_soyad,puan,gerekce\nTest Öğrenci Bir,5,Kanaat\n"
    assert load_adjustments(write_csv(tmp_path, text, encoding="utf-8-sig"))[0].points == 5


def test_adjustment_without_reason_stops_with_line_number(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,puan,gerekce\nTest Öğrenci Bir,10,\n")
    with pytest.raises(ValueError, match="line 2.*reason"):
        load_adjustments(path)


@pytest.mark.parametrize("points", ["abc", "7.5", ""])
def test_points_must_be_a_whole_number(tmp_path, points):
    path = write_csv(tmp_path, f"ad_soyad,puan,gerekce\nTest Öğrenci Bir,{points},Kanaat\n")
    with pytest.raises(ValueError, match="whole number"):
        load_adjustments(path)


# Error guessing — commas in Turkish numbers and sentences split the row


def test_decimal_comma_stops_with_error(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,puan,gerekce\nTest Öğrenci Bir,7,5,Kanaat\n")
    with pytest.raises(ValueError, match="too many columns"):
        load_adjustments(path)


def test_unquoted_reason_with_comma_stops_with_error(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,puan,gerekce\nTest Öğrenci Bir,10,Kanaat, ekip lideri\n")
    with pytest.raises(ValueError, match="in quotes"):
        load_adjustments(path)


def test_quoted_reason_with_comma_is_loaded(tmp_path):
    path = write_csv(tmp_path, 'ad_soyad,puan,gerekce\nTest Öğrenci Bir,10,"Kanaat, ekip lideri"\n')
    assert load_adjustments(path)[0].reason == "Kanaat, ekip lideri"


def test_missing_column_stops_with_error(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,puan\nTest Öğrenci Bir,10\n")
    with pytest.raises(ValueError, match="gerekce"):
        load_adjustments(path)


# REQ-3.11 — Adjustments are applied to the final grade


def test_adjustment_is_added_to_the_final_grade():
    result = report_for([Adjustment("Test Öğrenci Bir", 20, "Kanaat")])["Test Öğrenci Bir"]
    assert result.grade == 50
    assert result.final == 70


def test_student_without_adjustment_keeps_grade():
    result = report_for([])["Test Öğrenci Bir"]
    assert result.final == result.grade == 50


@pytest.mark.parametrize(
    ("name", "points", "expected"),
    [
        ("Test Öğrenci İki", 10, 100),  # 100 + 10 is limited to 100
        ("Test Öğrenci Bir", -60, 0),  # 50 - 60 is limited to 0
        ("Test Öğrenci Bir", -50, 0),  # exactly 0
        ("Test Öğrenci Bir", 50, 100),  # exactly 100
    ],
)
def test_final_grade_stays_between_0_and_100(name, points, expected):
    assert report_for([Adjustment(name, points, "Kanaat")])[name].final == expected


def test_name_is_matched_ignoring_turkish_letters_and_case():
    result = report_for([Adjustment("TEST OGRENCI BIR", 10, "Kanaat")])["Test Öğrenci Bir"]
    assert result.final == 60


def test_several_adjustments_for_one_student_are_added_up():
    adjustments = [
        Adjustment("Test Öğrenci Bir", 10, "Backlog SM tarafından açıldı"),
        Adjustment("Test Öğrenci Bir", 5, "Ekibi motive etti"),
    ]
    result = report_for(adjustments)["Test Öğrenci Bir"]
    assert result.final == 65
    assert result.reasons == ("+10: Backlog SM tarafından açıldı", "+5: Ekibi motive etti")


def test_adjustment_for_unknown_student_stops_with_error():
    with pytest.raises(ValueError, match="Test Öğrenci Dört"):
        report_for([Adjustment("Test Öğrenci Dört", 10, "Kanaat")])


def test_adjustment_for_unmatched_student_is_not_applied():
    student = Student(name="Test Öğrenci Bir", role="Back", emails=("bir@example.org",))
    adjustment = Adjustment("Test Öğrenci Bir", 10, "Kanaat")
    report = build_report([student], GitHubData(), TaigaData(), 1.0, [adjustment])
    assert report.students[0].final is None
    assert any("adjustment not applied" in w for w in report.warnings)
