"""Instructor adjustments with a written reason (REQ-3.11)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

NAME_COLUMN = "ad_soyad"
POINTS_COLUMN = "puan"
REASON_COLUMN = "gerekce"


@dataclass(frozen=True)
class Adjustment:
    name: str
    points: int
    reason: str


def load_adjustments(path: str | Path) -> list[Adjustment]:
    """Read the adjustments file: one row per adjustment, with name, points and reason."""
    with open(path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = [name.strip().lower() for name in reader.fieldnames or []]
        missing = [c for c in (NAME_COLUMN, POINTS_COLUMN, REASON_COLUMN) if c not in columns]
        if missing:
            raise ValueError(f"Adjustments file is missing columns: {', '.join(missing)}")
        reader.fieldnames = columns

        adjustments = []
        for row in reader:
            line = reader.line_num
            if row.get(None):
                # a comma inside a value splits the row: "7,5" or an unquoted reason
                raise ValueError(
                    f"Adjustments line {line}: too many columns. '{POINTS_COLUMN}' must be a "
                    'whole number, and a reason with a comma must be in quotes ("...")'
                )
            values = {k: (v or "").strip() for k, v in row.items() if k is not None}
            if not any(values.values()):
                continue
            if not values[NAME_COLUMN]:
                raise ValueError(f"Adjustments line {line}: '{NAME_COLUMN}' is empty")
            if not values[REASON_COLUMN]:
                raise ValueError(f"Adjustments line {line}: every adjustment needs a reason")
            try:
                points = int(values[POINTS_COLUMN])
            except ValueError:
                raise ValueError(
                    f"Adjustments line {line}: '{POINTS_COLUMN}' must be a whole number"
                ) from None
            adjustments.append(Adjustment(values[NAME_COLUMN], points, values[REASON_COLUMN]))
        return adjustments
