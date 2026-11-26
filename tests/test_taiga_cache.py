"""Tests for saved Taiga change histories (REQ-1.10).

Taiga is replaced by a fake; every test uses its own temporary folder.
"""

import pytest

from contribution_tool.taiga_cache import HistoryCache, cached_histories

HISTORY = [{"user": {"username": "ogrenciuc"}, "comment": "Kabul: 4 kriterin 4'ü sağlandı"}]


class FakeTaiga:
    """Counts logins and downloads."""

    def __init__(self):
        self.logins = 0
        self.asked = []

    def connect(self):
        self.logins += 1
        return self.send

    def send(self, path):
        self.asked.append(path)
        return HISTORY


def row(item_id="7", modified="2026-11-20T10:00:00+0000"):
    return {"id": item_id, "modified_date": modified}


@pytest.fixture
def cache(tmp_path):
    return HistoryCache(tmp_path / "taiga-history")


def test_first_run_downloads_and_saves(cache):
    taiga = FakeTaiga()
    assert cached_histories("userstory", [row()], cache, taiga.connect) == [HISTORY]
    assert taiga.asked == ["/history/userstory/7"]
    assert (cache.downloaded, cache.reused) == (1, 0)


def test_unchanged_item_is_not_downloaded_again_and_no_login_is_needed(cache):
    cached_histories("userstory", [row()], cache, FakeTaiga().connect)
    taiga = FakeTaiga()
    again = HistoryCache(cache.folder)  # as if the program was started again
    assert cached_histories("userstory", [row()], again, taiga.connect) == [HISTORY]
    assert (taiga.logins, taiga.asked) == (0, [])
    assert (again.downloaded, again.reused) == (0, 1)


def test_changed_item_is_downloaded_again(cache):
    cached_histories("userstory", [row()], cache, FakeTaiga().connect)
    taiga = FakeTaiga()
    cached_histories("userstory", [row(modified="2026-11-25T09:00:00+0000")], cache, taiga.connect)
    assert taiga.asked == ["/history/userstory/7"]


def test_item_without_modified_date_is_always_downloaded_and_not_saved(cache):
    for _ in range(2):
        cached_histories("task", [row(modified="")], cache, FakeTaiga().connect)
    assert cache.downloaded == 2
    assert not cache.folder.exists()


def test_same_id_of_another_kind_is_kept_apart(cache):
    cached_histories("userstory", [row()], cache, FakeTaiga().connect)
    taiga = FakeTaiga()
    cached_histories("task", [row()], cache, taiga.connect)
    assert taiga.asked == ["/history/task/7"]


def test_damaged_file_is_downloaded_again(cache):
    cached_histories("issue", [row()], cache, FakeTaiga().connect)
    for path in cache.folder.glob("*.json"):
        path.write_text("{ yarım", encoding="utf-8")
    taiga = FakeTaiga()
    assert cached_histories("issue", [row()], cache, taiga.connect) == [HISTORY]
    assert taiga.asked == ["/history/issue/7"]


def test_rows_without_id_are_skipped(cache):
    cached_histories("userstory", [row("2")], cache, FakeTaiga().connect)
    rows = [row("1"), {"id": "", "modified_date": ""}, row("2")]
    assert len(cached_histories("userstory", rows, cache, FakeTaiga().connect)) == 2


def test_csv_without_id_column_stops_with_error(cache):
    with pytest.raises(ValueError, match="'id' column"):
        cached_histories("userstory", [{"modified_date": "x"}], cache, FakeTaiga().connect)


def test_turkish_comments_are_kept_readable(cache):
    cached_histories("userstory", [row()], cache, FakeTaiga().connect)
    (path,) = cache.folder.glob("*.json")
    assert "sağlandı" in path.read_text(encoding="utf-8")
