"""Tests for date parsing and date ranges (REQ-1.3)."""

from datetime import date

import pytest

from contribution_tool.dates import in_range, parse_date

START = date(2026, 9, 21)
END = date(2026, 10, 19)


# REQ-1.3 — Boundary values: start and end days are included


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 9, 20), False),  # start - 1
        (date(2026, 9, 21), True),  # start
        (date(2026, 10, 19), True),  # end
        (date(2026, 10, 20), False),  # end + 1
    ],
)
def test_range_boundaries(day, expected):
    assert in_range(day, START, END) is expected


def test_no_range_includes_everything():
    assert in_range(date(2000, 1, 1))
    assert in_range(None)


def test_missing_date_is_excluded_when_range_is_given():
    assert not in_range(None, START, END)


def test_only_start_given():
    assert in_range(date(2030, 1, 1), start=START)
    assert not in_range(date(2026, 9, 20), start=START)


def test_only_end_given():
    assert in_range(date(2000, 1, 1), end=END)
    assert not in_range(date(2026, 10, 20), end=END)


# Date formats from Taiga and GitHub


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-10-01 10:00:00.123456+00:00", date(2026, 10, 1)),  # Taiga
        ("2026-10-01T10:00:00Z", date(2026, 10, 1)),  # GitHub
        ("2026-10-01", date(2026, 10, 1)),  # date only
        ("", None),
        (None, None),
        ("not a date", None),
    ],
)
def test_parse_date_formats(text, expected):
    assert parse_date(text) == expected


# Error guessing — a UTC time late in the evening is already the next day in Turkey


def test_utc_evening_is_next_day_in_turkey():
    # 21:30 UTC on 19 October is 00:30 on 20 October in Turkey (UTC+3)
    day = parse_date("2026-10-19T21:30:00Z")
    assert day == date(2026, 10, 20)
    assert not in_range(day, START, END)
