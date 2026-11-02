"""Tests for counting work from Taiga change history (REQ-1.8, REQ-1.9)."""

from datetime import date

import pytest

from contribution_tool.taiga_history import collect_history

START = date(2026, 9, 21)
END = date(2026, 10, 19)


def entry(username="ogrencibes", status=None, comment="", created="2026-10-05T10:00:00Z", **extra):
    values = {
        "user": {"username": username, "name": "Test Öğrenci Beş"} if username else None,
        "created_at": created,
        "values_diff": {"status": list(status)} if status else {},
        "comment": comment,
    }
    values.update(extra)
    return values


def counts(story_entries=(), other_entries=(), **dates):
    data = collect_history([list(story_entries)], [list(other_entries)], **dates)
    return data.counts["ogrencibes"]


# REQ-1.8 — Moving a user story to a done status is counted for the user who did it


@pytest.mark.parametrize("new_status", ["Done", "Bitti", "Kapandı", "CLOSED"])
def test_story_moved_to_done_status_is_counted(new_status):
    assert counts([entry(status=("Testte", new_status))])["stories_accepted"] == 1


def test_story_moved_to_other_status_is_not_counted():
    assert counts([entry(status=("Yapılıyor", "Testte"))])["stories_accepted"] == 0


def test_move_between_two_done_statuses_is_not_counted():
    assert counts([entry(status=("Done", "Closed"))])["stories_accepted"] == 0


def test_each_move_to_done_is_counted():
    moves = [entry(status=("Testte", "Done")), entry(status=("Testte", "Done"))]
    assert counts(moves)["stories_accepted"] == 2


def test_task_moved_to_done_is_not_a_story_acceptance():
    assert counts(other_entries=[entry(status=("Testte", "Done"))])["stories_accepted"] == 0


# REQ-1.9 — Comments are counted for the writer; deleted comments are not


def test_comment_on_story_is_counted():
    assert counts([entry(comment="Kabul kriteri 2 sağlanmıyor")])["taiga_comments"] == 1


def test_comment_on_task_or_issue_is_counted():
    assert counts(other_entries=[entry(comment="Tekrar ürettim")])["taiga_comments"] == 1


def test_empty_comment_is_not_counted():
    assert counts([entry(comment="   ")])["taiga_comments"] == 0


def test_deleted_comment_is_not_counted():
    deleted = entry(comment="Yanlış yazdım", delete_comment_date="2026-10-06T10:00:00Z")
    assert counts([deleted])["taiga_comments"] == 0


def test_status_change_with_comment_counts_both():
    both = entry(status=("Testte", "Done"), comment="Test edildi, geçti")
    result = counts([both])
    assert result["stories_accepted"] == 1
    assert result["taiga_comments"] == 1


# REQ-1.3 — Date range


def test_change_outside_range_is_not_counted():
    late = entry(status=("Testte", "Done"), created="2026-10-20T10:00:00Z")
    assert counts([late], start=START, end=END)["stories_accepted"] == 0


# Users from history are available for matching


def test_users_are_collected_with_full_names():
    data = collect_history([[entry(username="OgrenciBes", comment="Not")]])
    assert data.users == {"ogrencibes": "Test Öğrenci Beş"}


def test_entry_without_user_is_skipped():
    data = collect_history([[entry(username=None, status=("Testte", "Done"))]])
    assert data.users == {}
