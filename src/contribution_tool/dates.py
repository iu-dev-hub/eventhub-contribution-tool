"""Date parsing and date range checks (REQ-1.3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Turkey has used UTC+3 all year round since 2016
TURKEY = timezone(timedelta(hours=3))


def parse_date(text: str | None) -> date | None:
    """Read a date from Taiga or GitHub and return the calendar day in Turkey time.

    Returns None for empty or unreadable values.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(TURKEY)
    return moment.date()


def in_range(day: date | None, start: date | None = None, end: date | None = None) -> bool:
    """True when the day is inside the range; start and end days are included."""
    if start is None and end is None:
        return True
    if day is None:
        return False
    return (start is None or day >= start) and (end is None or day <= end)
