"""Tests for collecting contributions from Taiga CSV exports (REQ-1.2, REQ-1.5)."""

from datetime import date

import pytest

from contribution_tool.taiga import TaigaData, collect_taiga, load_csv, merge_taiga


def row(**values):
    base = {
        "owner": "",
        "owner_full_name": "",
        "assigned_to": "",
        "assigned_to_full_name": "",
        "status": "Yeni",
        "is_closed": "False",
        "created_date": "2026-10-01 10:00:00+00:00",
        "finished_date": "",
    }
    base.update(values)
    return base


def collect(stories=(), tasks=(), issues=(), **dates):
    return collect_taiga(stories, tasks, issues, **dates)


# REQ-1.2 — User stories, tasks and issues are counted


def test_story_counts_as_written_for_owner():
    data = collect(stories=[row(owner="ogrencibir")])
    assert data.counts["ogrencibir"]["stories_written"] == 1


def test_closed_story_counts_as_done_for_assignee():
    story = row(assigned_to="ogrenciiki", is_closed="True", finished_date="2026-10-05")
    assert collect(stories=[story]).counts["ogrenciiki"]["stories_done"] == 1


def test_open_story_does_not_count_as_done():
    story = row(assigned_to="ogrenciiki", is_closed="False")
    assert collect(stories=[story]).counts["ogrenciiki"]["stories_done"] == 0


def test_closed_task_counts_for_assignee():
    task = row(assigned_to="ogrenciuc", is_closed="True", finished_date="2026-10-05")
    assert collect(tasks=[task]).counts["ogrenciuc"]["tasks_closed"] == 1


def test_issue_counts_as_reported_for_owner_and_fixed_for_assignee():
    issue = row(
        owner="ogrencibes",
        assigned_to="ogrencidort",
        status="Kapandı",
        is_closed="True",
        finished_date="2026-10-06",
    )
    data = collect(issues=[issue])
    assert data.counts["ogrencibes"]["bugs_reported"] == 1
    assert data.counts["ogrencidort"]["bugs_fixed"] == 1


def test_usernames_are_lowercased():
    data = collect(stories=[row(owner="OgrenciBir")])
    assert data.counts["ogrencibir"]["stories_written"] == 1


def test_users_are_collected_with_full_names():
    story = row(owner="ogrencibir", owner_full_name="Test Öğrenci Bir", assigned_to="iki")
    data = collect(stories=[story])
    assert data.users == {"ogrencibir": "Test Öğrenci Bir", "iki": ""}


# REQ-1.5 — Rejected issues are not counted


@pytest.mark.parametrize("status", ["Reddedildi", "REDDEDİLDİ", "Rejected"])
def test_rejected_issue_is_not_counted(status):
    issue = row(owner="ogrencibes", assigned_to="ogrencidort", status=status, is_closed="True")
    data = collect(issues=[issue])
    assert data.counts["ogrencibes"]["bugs_reported"] == 0
    assert data.counts["ogrencidort"]["bugs_fixed"] == 0


# REQ-1.3 — Date range is applied


def test_story_created_before_range_is_not_counted():
    story = row(owner="ogrencibir", created_date="2026-09-20 12:00:00+00:00")
    data = collect(stories=[story], start=date(2026, 9, 21), end=date(2026, 10, 19))
    assert data.counts["ogrencibir"]["stories_written"] == 0


def test_task_finished_after_range_is_not_counted():
    task = row(assigned_to="ogrenciuc", is_closed="True", finished_date="2026-10-20")
    data = collect(tasks=[task], start=date(2026, 9, 21), end=date(2026, 10, 19))
    assert data.counts["ogrenciuc"]["tasks_closed"] == 0


def test_story_export_with_finish_date_column_is_accepted():
    story = row(assigned_to="ogrenciiki", is_closed="True")
    del story["finished_date"]
    story["finish_date"] = "2026-10-05"
    assert collect(stories=[story]).counts["ogrenciiki"]["stories_done"] == 1


# Risk from the test plan — a missing column stops with a clear error


def test_missing_column_stops_with_error():
    story = row(owner="ogrencibir")
    del story["is_closed"]
    with pytest.raises(ValueError, match="is_closed"):
        collect(stories=[story])


# REQ-1.2 — CSV is read from a file or a URL


def test_load_csv_from_file_with_bom(tmp_path):
    path = tmp_path / "issues.csv"
    path.write_text("Owner,Status\nogrencibir,Yeni\n", encoding="utf-8-sig")
    assert load_csv(path) == [{"owner": "ogrencibir", "status": "Yeni"}]


def test_load_csv_from_url(monkeypatch):
    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(url, timeout):
        assert url == "https://example.org/issues.csv"
        return FakeResponse(b"owner,status\nogrencibir,Yeni\n")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert load_csv("https://example.org/issues.csv") == [{"owner": "ogrencibir", "status": "Yeni"}]


# CSV data and history data are combined


def test_merge_adds_up_counts():
    csv_data = collect(stories=[row(owner="ogrencibir")])
    history = TaigaData()
    history.counts["ogrencibir"]["stories_accepted"] += 2
    merged = merge_taiga(csv_data, history)
    assert merged.counts["ogrencibir"] == {"stories_written": 1, "stories_accepted": 2}


def test_merge_keeps_full_names_from_either_source():
    csv_data = collect(stories=[row(owner="ogrencibir")])  # no full name in the CSV
    history = TaigaData(users={"ogrencibir": "Test Öğrenci Bir", "ogrencibes": "Test Öğrenci Beş"})
    merged = merge_taiga(csv_data, history)
    assert merged.users == {"ogrencibir": "Test Öğrenci Bir", "ogrencibes": "Test Öğrenci Beş"}
