"""Collecting contributions from Taiga CSV exports (REQ-1.2, REQ-1.3, REQ-1.5)."""

from __future__ import annotations

import csv
import io
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from contribution_tool.dates import in_range, parse_date
from contribution_tool.matching import normalize_name

REJECTED = {"reddedildi", "rejected"}
REQUIRED_COLUMNS = ("owner", "assigned_to", "status", "is_closed", "created_date")
FINISHED_COLUMNS = ("finished_date", "finish_date")

Row = Mapping[str, str]


@dataclass
class TaigaData:
    counts: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    users: dict[str, str] = field(default_factory=dict)


def load_csv(source: str | Path) -> list[dict[str, str]]:
    """Read a Taiga CSV export from a file path or a URL (REQ-1.2)."""
    text = str(source)
    if text.startswith(("http://", "https://")):
        with urllib.request.urlopen(text, timeout=60) as response:
            content = response.read().decode("utf-8-sig")
    else:
        content = Path(source).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    return [
        {key.strip().lower(): (value or "").strip() for key, value in row.items() if key}
        for row in reader
    ]


def collect_taiga(
    stories: Iterable[Row],
    tasks: Iterable[Row],
    issues: Iterable[Row],
    start: date | None = None,
    end: date | None = None,
) -> TaigaData:
    """Count Taiga contributions per username inside the date range."""
    data = TaigaData()

    for row in _checked(stories, "stories"):
        _remember_users(data, row)
        if row["owner"] and in_range(parse_date(row["created_date"]), start, end):
            data.counts[row["owner"].lower()]["stories_written"] += 1
        if _closed_by_assignee(row, start, end):
            data.counts[row["assigned_to"].lower()]["stories_done"] += 1

    for row in _checked(tasks, "tasks"):
        _remember_users(data, row)
        if _closed_by_assignee(row, start, end):
            data.counts[row["assigned_to"].lower()]["tasks_closed"] += 1

    for row in _checked(issues, "issues"):
        _remember_users(data, row)
        if normalize_name(row["status"]) in REJECTED:  # REQ-1.5
            continue
        if row["owner"] and in_range(parse_date(row["created_date"]), start, end):
            data.counts[row["owner"].lower()]["bugs_reported"] += 1
        if _closed_by_assignee(row, start, end):
            data.counts[row["assigned_to"].lower()]["bugs_fixed"] += 1

    return data


def _checked(rows: Iterable[Row], name: str) -> list[Row]:
    rows = list(rows)
    if not rows:
        return rows
    columns = rows[0].keys()
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if not any(c in columns for c in FINISHED_COLUMNS):
        missing.append(" or ".join(FINISHED_COLUMNS))
    if missing:
        raise ValueError(f"Taiga {name} CSV is missing columns: {', '.join(missing)}")
    return rows


def _finished(row: Row) -> date | None:
    for column in FINISHED_COLUMNS:
        if row.get(column):
            return parse_date(row[column])
    return None


def _closed_by_assignee(row: Row, start: date | None, end: date | None) -> bool:
    closed = row["is_closed"].lower() in {"true", "1", "yes"}
    return bool(row["assigned_to"]) and closed and in_range(_finished(row), start, end)


def _remember_users(data: TaigaData, row: Row) -> None:
    for user_column, name_column in (
        ("owner", "owner_full_name"),
        ("assigned_to", "assigned_to_full_name"),
    ):
        username = row.get(user_column, "").lower()
        if username:
            # keep the account even without a full name, so it can match by username
            full_name = row.get(name_column) or data.users.get(username, "")
            data.users[username] = full_name

def merge_taiga(*parts: TaigaData) -> TaigaData:
    """Combine Taiga data from the CSV export and from the change history."""
    merged = TaigaData()
    for part in parts:
        for user, counts in part.counts.items():
            merged.counts[user].update(counts)
        for user, full_name in part.users.items():
            merged.users[user] = full_name or merged.users.get(user, "")
    return merged
