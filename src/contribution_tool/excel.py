"""Writing the report to an Excel file (REQ-5.1)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from contribution_tool.report import Report
from contribution_tool.scoring import METRICS

UNMATCHED = "UNMATCHED"
HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
UNMATCHED_FILL = PatternFill("solid", fgColor="F8CBAD")
GRADE_COLUMNS = ["Student", "Role", "Grade", "Adjustment", "Final", "Score", "Accounts"]


def write_excel(report: Report, path: str | Path, title: str = "") -> Path:
    """Write grades, warnings, adjustments and unlinked accounts to one workbook."""
    workbook = Workbook()
    grades = workbook.active
    grades.title = "Grades"
    _grades_sheet(grades, report, title)
    _list_sheet(workbook.create_sheet("Warnings"), "Warning", report.warnings)
    adjustments = [(r.name, reason) for r in report.students for reason in r.reasons]
    _table_sheet(workbook.create_sheet("Adjustments"), ["Student", "Adjustment"], adjustments)
    _list_sheet(workbook.create_sheet("Unlinked accounts"), "Account", report.unlinked)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def _header(sheet, row: int, names: list[str]) -> None:
    for column, name in enumerate(names, 1):
        cell = sheet.cell(row, column, name)
        cell.font, cell.fill = HEADER_FONT, HEADER_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)


def _grades_sheet(sheet, report: Report, title: str) -> None:
    sheet["A1"] = title or "Contribution grades"
    sheet["A1"].font = Font(bold=True, size=13)
    names = GRADE_COLUMNS + list(METRICS)
    _header(sheet, 3, names)
    for row, r in enumerate(report.students, 4):
        values = [
            r.name,
            r.role,
            UNMATCHED if r.unmatched else r.grade,
            r.adjustment or None,
            r.final,
            round(r.score, 2),
            ", ".join(r.accounts),
        ] + [r.counts.get(metric, 0) for metric in METRICS]
        for column, value in enumerate(values, 1):
            sheet.cell(row, column, value)
        if r.unmatched:
            for column in range(1, len(GRADE_COLUMNS) + 1):
                sheet.cell(row, column).fill = UNMATCHED_FILL

    last = 3 + len(report.students)
    final = get_column_letter(GRADE_COLUMNS.index("Final") + 1)
    sheet.conditional_formatting.add(
        f"{final}4:{final}{max(last, 4)}",
        ColorScaleRule(
            start_type="num",
            start_value=0,
            start_color="F8696B",
            mid_type="num",
            mid_value=60,
            mid_color="FFEB84",
            end_type="num",
            end_value=100,
            end_color="63BE7B",
        ),
    )
    sheet.freeze_panes = "C4"
    sheet.auto_filter.ref = f"A3:{get_column_letter(len(names))}{max(last, 3)}"
    sheet.column_dimensions["A"].width = 26
    sheet.column_dimensions["B"].width = 14
    sheet.column_dimensions["G"].width = 28
    for column in range(len(GRADE_COLUMNS) + 1, len(names) + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 12


def _list_sheet(sheet, name: str, values: list[str]) -> None:
    _table_sheet(sheet, [name], [(value,) for value in values])


def _table_sheet(sheet, names: list[str], rows: list[tuple]) -> None:
    _header(sheet, 1, names)
    for row in rows:
        sheet.append(list(row))
    for column in range(1, len(names) + 1):
        sheet.column_dimensions[get_column_letter(column)].width = (
            60 if column == len(names) else 26
        )
