"""Loading the instructor's student list (REQ-2.1)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

NAME_COLUMN = "ad_soyad"
ROLE_PREFIX = "rol"


@dataclass(frozen=True)
class Student:
    name: str
    role: str = ""
    emails: tuple[str, ...] = ()
    usernames: tuple[str, ...] = ()


def normalize_identifier(value: str) -> str:
    """Trim spaces and lowercase an e-mail address or username."""
    return value.strip().lower()


def load_students(path: str | Path, role_column: str | None = None) -> list[Student]:
    """Read the student list. Values with '@' are e-mails, other values are usernames."""
    # utf-8-sig also reads files that Excel saves with a byte order mark (BOM)
    with open(path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("Student list is empty")
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
        columns = reader.fieldnames

        if NAME_COLUMN not in columns:
            raise ValueError(f"Student list must have a '{NAME_COLUMN}' column")

        role_columns = [c for c in columns if c.startswith(ROLE_PREFIX)]
        if role_column is None:
            selected_role = role_columns[0] if role_columns else None
        elif role_column.lower() in role_columns:
            selected_role = role_column.lower()
        else:
            raise ValueError(f"Role column '{role_column}' not found. Available: {role_columns}")
        id_columns = [c for c in columns if c != NAME_COLUMN and c not in role_columns]

        students = []
        for row in reader:
            values = {k: (v or "").strip() for k, v in row.items() if k is not None}
            if not any(values.values()):
                continue
            name = values.get(NAME_COLUMN, "")
            if not name:
                raise ValueError(f"Line {reader.line_num}: '{NAME_COLUMN}' is empty")
            ids = [normalize_identifier(values[c]) for c in id_columns if values.get(c)]
            students.append(
                Student(
                    name=name,
                    role=values.get(selected_role, "") if selected_role else "",
                    emails=tuple(i for i in ids if "@" in i),
                    usernames=tuple(i for i in ids if "@" not in i),
                )
            )
        return students
