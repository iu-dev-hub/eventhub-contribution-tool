"""Tests for reading Taiga exports from saved links (REQ-1.2, REQ-6.5)."""

import pytest

from contribution_tool.taiga import load_exports_from_config

CSV = "id,owner,status\n7,ogrencibir,New\n"


def write_config(tmp_path, text):
    path = tmp_path / "taiga-links.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_three_exports_are_read_from_the_links(tmp_path, monkeypatch):
    asked = []

    class FakeResponse:
        def read(self):
            return CSV.encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(url, timeout):
        asked.append(url)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    config = write_config(
        tmp_path,
        'userstories = "https://example.org/us?uuid=a"\n'
        'tasks = "https://example.org/t?uuid=b"\n'
        'issues = " https://example.org/i?uuid=c "\n',
    )
    stories, tasks, issues = load_exports_from_config(config)
    assert stories == [{"id": "7", "owner": "ogrencibir", "status": "New"}]
    assert asked == [
        "https://example.org/us?uuid=a",
        "https://example.org/t?uuid=b",
        "https://example.org/i?uuid=c",
    ]


def test_missing_config_file_stops_with_instructions(tmp_path):
    with pytest.raises(FileNotFoundError, match="Settings → Project → Reports"):
        load_exports_from_config(tmp_path / "missing.toml")


def test_missing_link_stops_with_error(tmp_path):
    config = write_config(tmp_path, 'userstories = "https://example.org/us"\ntasks = ""\n')
    with pytest.raises(ValueError, match="tasks, issues"):
        load_exports_from_config(config)
