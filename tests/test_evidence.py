"""Tests for keeping contributions with their text and link (REQ-7.1)."""

from datetime import date

import pytest

from contribution_tool.evidence import Evidence
from contribution_tool.github import collect_github
from contribution_tool.taiga import TaigaData, collect_taiga, merge_taiga
from contribution_tool.taiga_history import collect_history

START = date(2026, 9, 21)
END = date(2026, 10, 19)


def by_kind(evidence, kind):
    return [e for e in evidence if e.kind == kind]


PR = {
    "number": 12,
    "title": "Bilet iade servisi",
    "body": "Closes TG-41. BR-4.4 sınır değerleri test edildi.",
    "url": "https://example.org/pull/12",
    "author": {"login": "OgrenciBir"},
    "createdAt": "2026-10-01T10:00:00Z",
    "mergedAt": None,
    "reviews": {
        "nodes": [
            {
                "author": {"login": "ogrenciiki"},
                "submittedAt": "2026-10-02T10:00:00Z",
                "body": "Genel olarak iyi.",
                "comments": {
                    "totalCount": 1,
                    "nodes": [{"path": "services.py", "body": "zorunlu: 48. saat eksik"}],
                },
            }
        ]
    },
    "commits": {"nodes": []},
}

DISCUSSION = {
    "title": "Günlük 2. hafta",
    "url": "https://example.org/discussions/3",
    "body": "Dün: model. Bugün: servis. Engel: yok.",
    "author": {"login": "ogrencibir"},
    "createdAt": "2026-10-03T10:00:00Z",
    "comments": {"nodes": []},
}


# GitHub


def test_pull_request_is_kept_with_its_description():
    pr = by_kind(collect_github([PR]).evidence, "pull_request")[0]
    assert pr.author == "ogrencibir"
    assert pr.title == "PR #12: Bilet iade servisi"
    assert "BR-4.4" in pr.text
    assert pr.url == "https://example.org/pull/12"
    assert pr.item_id == "github:pr:12"


def test_code_review_keeps_body_and_line_comments():
    review = by_kind(collect_github([PR]).evidence, "code_review")[0]
    assert review.author == "ogrenciiki"
    assert review.text == "Genel olarak iyi.\n[services.py] zorunlu: 48. saat eksik"


def test_discussion_post_is_kept():
    post = by_kind(collect_github([], [DISCUSSION]).evidence, "discussion_post")[0]
    assert post.title == "Günlük 2. hafta"
    assert post.text.startswith("Dün:")


def test_github_evidence_follows_the_date_range():
    data = collect_github([PR], [DISCUSSION], start=date(2026, 10, 3), end=END)
    assert [e.kind for e in data.evidence] == ["discussion_post"]


# Taiga


def taiga_row(**values):
    base = {
        "id": "7",
        "ref": "41",
        "subject": "Bilet iadesi",
        "description": "Given bilet alındı, When 48 saat kala iade, Then ücret iade edilir",
        "owner": "ogrencibes",
        "assigned_to": "",
        "status": "New",
        "is_closed": "False",
        "created_date": "2026-10-01 10:00:00+00:00",
        "finished_date": "",
    }
    base.update(values)
    return base


def test_user_story_is_kept_with_its_description():
    story = collect_taiga([taiga_row()], [], []).evidence[0]
    assert (story.kind, story.author, story.title) == (
        "user_story",
        "ogrencibes",
        "#41 Bilet iadesi",
    )
    assert story.text.startswith("Given")
    assert story.item_id == "taiga:us:7"


def test_bug_report_is_kept_but_rejected_issue_is_not():
    issues = [taiga_row(id="8", ref="50"), taiga_row(id="9", ref="51", status="Rejected")]
    evidence = collect_taiga([], [], issues).evidence
    assert [(e.kind, e.item_id) for e in evidence] == [("bug_report", "taiga:issue:8")]


def test_taiga_evidence_follows_the_date_range():
    data = collect_taiga([taiga_row()], [], [], start=date(2026, 10, 2), end=END)
    assert data.evidence == []


def test_taiga_comment_is_kept_but_deleted_comment_is_not():
    entry = {
        "id": "h1",
        "user": {"username": "ogrencibes", "name": "Test Öğrenci Beş"},
        "created_at": "2026-10-05T10:00:00Z",
        "values_diff": {},
        "comment": " Kabul kriteri 2 sağlanmıyor ",
    }
    deleted = {**entry, "id": "h2", "delete_comment_date": "2026-10-06T10:00:00Z"}
    evidence = collect_history([[entry, deleted]]).evidence
    assert [(e.kind, e.text, e.item_id) for e in evidence] == [
        ("taiga_comment", "Kabul kriteri 2 sağlanmıyor", "taiga:comment:h1")
    ]


def test_merge_keeps_evidence_from_both_sources():
    csv_data = collect_taiga([taiga_row()], [], [])
    history = TaigaData()
    history.evidence.append(
        Evidence("taiga_comment", "ogrencibes", None, "Taiga comment", "Not", "", "taiga:comment:x")
    )
    assert len(merge_taiga(csv_data, history).evidence) == 2


def test_unknown_kind_is_rejected():
    with pytest.raises(ValueError, match="commit"):
        Evidence("commit", "x", None, "", "", "", "id")
