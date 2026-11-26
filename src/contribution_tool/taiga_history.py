"""Counting work from Taiga change history (REQ-1.8, REQ-1.9).

The CSV export only shows who owns and who is assigned to an item. The change history
shows who moved a story to "Done" (testers, product owners) and who wrote comments.
This module processes history entries that have already been downloaded.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from contribution_tool.dates import in_range, parse_date
from contribution_tool.evidence import Evidence
from contribution_tool.matching import normalize_name
from contribution_tool.taiga import TaigaData

DONE_STATUSES = frozenset({"bitti", "done", "kapandi", "closed"})

# Comments written by the GitHub integration when a commit or pull request mentions an
# item, e.g. "This task has been mentioned by ... in the commit ..." (REQ-1.9)
AUTOMATIC_COMMENT = re.compile(r"^\s*this (task|user story|issue|epic) has been\b", re.IGNORECASE)

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
                _add_comment(data, user, entry)

    for history in other_histories:
        for entry in history:
            user = _username(data, entry)
            if not user or not in_range(parse_date(entry.get("created_at")), start, end):
                continue
            if _is_comment(entry):
                _add_comment(data, user, entry)
    return data


def _add_comment(data: TaigaData, user: str, entry: Entry) -> None:
    """Count a comment and keep its text (REQ-1.9, REQ-7.1)."""
    data.counts[user]["taiga_comments"] += 1
    data.evidence.append(
        Evidence(
            kind="taiga_comment",
            author=user,
            created=parse_date(entry.get("created_at")),
            title="Taiga comment",
            text=entry["comment"].strip(),
            url="",
            item_id=f"taiga:comment:{entry.get('id') or entry.get('created_at')}",
        )
    )


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
    """A comment written by a person: not empty, not deleted, not from the integration."""
    text = (entry.get("comment") or "").strip()
    return bool(text) and not entry.get("delete_comment_date") and not AUTOMATIC_COMMENT.match(text)
