"""Tests for writing the report to an Excel file (REQ-5.1)."""

from openpyxl import load_workbook

from contribution_tool.excel import write_excel
from contribution_tool.report import Report, StudentResult


def result(name, grade, adjustment=0, reasons=(), counts=None):
    return StudentResult(
        name=name,
        role="Back",
        accounts=("ogrencibir",) if grade is not None else (),
        methods=(),
        counts=counts or {},
        score=4.0,
        grade=grade,
        adjustment=adjustment,
        reasons=reasons,
    )


REPORT = Report(
    students=[
        result("Test Öğrenci Bir", 80, 10, ("+10: Kanaat",), {"pr_merged": 2}),
        result("Test Öğrenci Üç", None),
    ],
    targets={"Back": 4.0},
    unlinked=["hoca"],
    warnings=["Test Öğrenci Üç: not matched to any GitHub or Taiga account"],
)


def rows(sheet, start):
    return [list(row) for row in sheet.iter_rows(min_row=start, values_only=True)]


def test_workbook_has_all_sheets(tmp_path):
    book = load_workbook(write_excel(REPORT, tmp_path / "out.xlsx"))
    assert book.sheetnames == [
        "Grades",
        "Guidance",
        "Warnings",
        "Adjustments",
        "Unlinked accounts",
    ]


def test_grades_sheet_shows_grade_adjustment_final_and_counts(tmp_path):
    sheet = load_workbook(write_excel(REPORT, tmp_path / "out.xlsx"))["Grades"]
    header = rows(sheet, 3)[0]
    first = dict(zip(header, rows(sheet, 4)[0], strict=True))
    assert first["Student"] == "Test Öğrenci Bir"
    assert (first["Grade"], first["Adjustment"], first["Final"]) == (80, 10, 90)
    assert first["pr_merged"] == 2
    assert first["Accounts"] == "ogrencibir"


def test_unmatched_student_is_marked(tmp_path):
    sheet = load_workbook(write_excel(REPORT, tmp_path / "out.xlsx"))["Grades"]
    second = rows(sheet, 5)[0]
    assert second[2] == "UNMATCHED"
    assert second[4] is None
    assert sheet.cell(5, 1).fill.fgColor.rgb.endswith("F8CBAD")


def test_warnings_adjustments_and_unlinked_accounts_are_listed(tmp_path):
    book = load_workbook(write_excel(REPORT, tmp_path / "out.xlsx"))
    assert rows(book["Warnings"], 2) == [[REPORT.warnings[0]]]
    assert rows(book["Adjustments"], 2) == [["Test Öğrenci Bir", "+10: Kanaat"]]
    assert rows(book["Unlinked accounts"], 2) == [["hoca"]]


def test_final_grade_has_a_color_scale(tmp_path):
    sheet = load_workbook(write_excel(REPORT, tmp_path / "out.xlsx"))["Grades"]
    ranges = [str(r.sqref) for r in sheet.conditional_formatting]
    assert ranges == ["E4:E5"]


def test_title_is_written(tmp_path):
    sheet = load_workbook(write_excel(REPORT, tmp_path / "out.xlsx", "Dönem 1"))["Grades"]
    assert sheet["A1"].value == "Dönem 1"


def test_missing_folder_is_created(tmp_path):
    path = write_excel(REPORT, tmp_path / "data" / "reports" / "out.xlsx")
    assert path.exists()


# REQ-4 — Guidance sheet


def test_guidance_sheet_has_focus_for_matched_students_only(tmp_path):
    sheet = load_workbook(write_excel(REPORT, tmp_path / "out.xlsx"))["Guidance"]
    header = rows(sheet, 3)[0]
    students = rows(sheet, 4)
    assert [row[0] for row in students] == ["Test Öğrenci Bir"]
    assert header[-1] == "Focus"
    assert students[0][-1]
