"""Counting contributions from GitHub data (REQ-1.1, REQ-1.4, REQ-1.6).

This module only processes data that has already been downloaded; it does not call
the GitHub API. Pull requests and discussions are given in the shape of GitHub's
GraphQL API.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from contribution_tool.dates import in_range, parse_date

Node = Mapping[str, Any]


@dataclass
class GitHubData:
    counts: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    emails: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    @property
    def users(self) -> set[str]:
        """GitHub logins that have at least one counted contribution."""
        return {login for login, counts in self.counts.items() if sum(counts.values()) > 0}


def login_of(node: Node | None) -> str | None:
    """Lowercased login of a node's author; None for bots and deleted accounts (REQ-1.4)."""
    author = (node or {}).get("author") or {}
    login = (author.get("login") or "").lower()
    if not login or login.endswith("[bot]") or login == "ghost":
        return None
    return login


def collect_github(
    pull_requests: Iterable[Node],
    discussions: Iterable[Node] = (),
    start: date | None = None,
    end: date | None = None,
) -> GitHubData:
    """Count GitHub contributions per login inside the date range."""
    data = GitHubData()
    for pr in pull_requests:
        _count_pull_request(data, pr, start, end)
    for discussion in discussions:
        _count_discussion(data, discussion, start, end)
    return data


def _count_pull_request(data: GitHubData, pr: Node, start: date | None, end: date | None) -> None:
    author = login_of(pr)
    if author:
        if in_range(parse_date(pr.get("createdAt")), start, end):
            data.counts[author]["pr_opened"] += 1
        if pr.get("mergedAt") and in_range(parse_date(pr["mergedAt"]), start, end):
            data.counts[author]["pr_merged"] += 1

    reviewers = set()
    for review in (pr.get("reviews") or {}).get("nodes", []):
        reviewer = login_of(review)
        if not reviewer or reviewer == author:  # REQ-1.4, REQ-1.6
            continue
        if not in_range(parse_date(review.get("submittedAt")), start, end):
            continue
        reviewers.add(reviewer)
        comments = (review.get("comments") or {}).get("totalCount", 0)
        data.counts[reviewer]["review_comments"] += comments
    for reviewer in reviewers:  # several reviews on the same PR count as one
        data.counts[reviewer]["reviews"] += 1

    # Commit e-mails link accounts to students (REQ-2.2); they are not contributions
    for node in (pr.get("commits") or {}).get("nodes", []):
        commit_author = (node.get("commit") or {}).get("author") or {}
        login = login_of({"author": commit_author.get("user")})
        email = (commit_author.get("email") or "").strip().lower()
        if login and email:
            data.emails[email].add(login)


def _count_discussion(
    data: GitHubData, discussion: Node, start: date | None, end: date | None
) -> None:
    posts = [discussion]
    for comment in (discussion.get("comments") or {}).get("nodes", []):
        posts.append(comment)
        posts.extend((comment.get("replies") or {}).get("nodes", []))
    for post in posts:
        login = login_of(post)
        if login and in_range(parse_date(post.get("createdAt")), start, end):
            data.counts[login]["discussion_posts"] += 1
