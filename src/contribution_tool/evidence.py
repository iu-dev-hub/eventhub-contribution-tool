"""Contribution records with their text and link (REQ-7.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

KINDS = (
    "pull_request",
    "code_review",
    "discussion_post",
    "user_story",
    "bug_report",
    "taiga_comment",
)


@dataclass(frozen=True)
class Evidence:
    kind: str  # one of KINDS
    author: str  # lowercased GitHub login or Taiga username
    created: date | None
    title: str
    text: str
    url: str
    item_id: str  # stable id, e.g. "github:pr:12"

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"Unknown evidence kind '{self.kind}', expected one of {KINDS}")
