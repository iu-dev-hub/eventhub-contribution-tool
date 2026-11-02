"""Counting work from Taiga change history (REQ-1.8, REQ-1.9).

The CSV export only shows who owns and who is assigned to an item. The change history
shows who moved a story to "Done" (testers, product owners) and who wrote comments.
This module processes history entries that have already been downloaded.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from contribution_tool.dates import in_range, parse_date
from contribution_tool.matching import normalize_name
from contribution_tool.taiga import TaigaData

DONE_STATUSES = frozenset({"bitti", "done", "kapandi", "closed"})

Entry = Mapping[str, Any]


def collect_history(
    story_histories: Iterable[Iterable[Entry]],
    other_histories: Iterable[Iterable[Entry]] = (),
    start: date | None = None,
    end: date | None = None,
    done_statuses: frozenset[str] = DONE_STATUSES,
) -> TaigaData:
    """Count stories moved to a done status and comments, per Taiga username.

    story_histories: one list of history entries per user story
    other_histories: one list of history entries per task or issue (only comments count)
    """
    data = TaigaData()
    for history in story_histories:
        for entry in history:
            user = _username(data, entry)
            if not user or not in_range(parse_date(entry.get("created_at")), start, end):
                continue
            if _moved_to_done(entry, done_statuses):
                data.counts[user]["stories_accepted"] += 1
            if _is_comment(entry):
                data.counts[user]["taiga_comments"] += 1

    for history in other_histories:
        for entry in history:
            user = _username(data, entry)
            if not user or not in_range(parse_date(entry.get("created_at")), start, end):
                continue
            if _is_comment(entry):
                data.counts[user]["taiga_comments"] += 1
    return data


def _username(data: TaigaData, entry: Entry) -> str | None:
    user = entry.get("user") or {}
    username = (user.get("username") or "").lower()
    if not username:
        return None
    data.users[username] = user.get("name") or data.users.get(username, "")
    return username


def _moved_to_done(entry: Entry, done_statuses: frozenset[str]) -> bool:
    change = (entry.get("values_diff") or {}).get("status")
    if not change or len(change) != 2:
        return False
    old, new = (normalize_name(str(value or "")) for value in change)
    # moving between two done statuses (e.g. "Done" to "Closed") is not new work
    return new in done_statuses and old not in done_statuses


def _is_comment(entry: Entry) -> bool:
    return bool((entry.get("comment") or "").strip()) and not entry.get("delete_comment_date")
