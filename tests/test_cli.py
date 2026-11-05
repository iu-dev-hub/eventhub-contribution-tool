"""Tests for the command line interface (REQ-5.3).

GitHub is replaced by fake functions; no test connects to the internet.
"""

import pytest

from contribution_tool import cli

STUDENTS = (
    "ad_soyad,rol_d1,github\n"
    "Test Öğrenci Bir,Back,ogrencibir\n"
    "Test Öğrenci İki,Back,ogrenciiki\n"
    "Test Öğrenci Üç,Back,ogrenciuc\n"
)

PULL_REQUESTS = [
    {
        "author": {"login": login},
        "createdAt": "2026-10-01T10:00:00Z",
        "mergedAt": "2026-10-02T10:00:00Z",
        "reviews": {"nodes": []},
        "commits": {"nodes": []},
    }
    for login in ("ogrencibir", "ogrenciiki", "ogrenciiki", "hoca")
]

TAIGA_HEADER = "owner,assigned_to,status,is_closed,created_date,finished_date\n"


@pytest.fixture
def fake_github(monkeypatch):
    monkeypatch.setattr(cli, "get_token", lambda: "test-token")
    monkeypatch.setattr(cli, "fetch_pull_requests", lambda repo, send: PULL_REQUESTS)
    monkeypatch.setattr(cli, "fetch_discussions", lambda repo, send: [])


@pytest.fixture
def fake_taiga(monkeypatch):
    """Taiga login and history download replaced by fakes; returns the fake request."""
    asked = []
    histories = {}

    def fake_send(path):
        asked.append(path)
        return histories.get(path, [])

    monkeypatch.setattr(cli, "get_credentials", lambda: ("hoca", "gizli"))
    monkeypatch.setattr(cli, "login", lambda username, password: "test-token")
    monkeypatch.setattr(cli, "taiga_request", lambda token: fake_send)
    fake_send.histories = histories
    fake_send.asked = asked
    return fake_send


@pytest.fixture
def students_csv(tmp_path):
    path = tmp_path / "ogrenciler.csv"
    path.write_text(STUDENTS, encoding="utf-8")
    return path


def write_taiga(folder, files=cli.TAIGA_FILES):
    folder.mkdir()
    for name in files:
        (folder / name).write_text(TAIGA_HEADER, encoding="utf-8")
    return folder


# REQ-5.3 — One command runs the whole tool and prints a summary


def test_full_run_prints_grades(fake_github, fake_taiga, students_csv, tmp_path, capsys):
    taiga = write_taiga(tmp_path / "taiga")
    code = cli.main(["--students", str(students_csv), "--taiga", str(taiga), "--role", "rol_d1"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Test Öğrenci Bir" in output
    assert "Test Öğrenci İki" in output
    assert "100" in output


def test_run_without_taiga_folder(fake_github, students_csv, capsys):
    assert cli.main(["--students", str(students_csv)]) == 0
    assert "Test Öğrenci Bir" in capsys.readouterr().out


def test_unmatched_student_is_shown(fake_github, students_csv, capsys):
    cli.main(["--students", str(students_csv)])
    output = capsys.readouterr().out
    assert "UNMATCHED" in output
    assert "Test Öğrenci Üç: not matched" in output


def test_unlinked_accounts_are_shown(fake_github, students_csv, capsys):
    cli.main(["--students", str(students_csv)])
    assert "  - hoca" in capsys.readouterr().out


# Errors stop the tool with a message and exit code 1


def test_missing_token_stops_with_message(monkeypatch, students_csv, capsys):
    monkeypatch.delenv("CONTRIBUTION_TOOL_TOKEN", raising=False)
    assert cli.main(["--students", str(students_csv)]) == 1
    assert "CONTRIBUTION_TOOL_TOKEN" in capsys.readouterr().err


def test_missing_taiga_file_stops_with_message(
    fake_github, fake_taiga, students_csv, tmp_path, capsys
):
    taiga = write_taiga(tmp_path / "taiga", files=("userstories.csv", "tasks.csv"))
    assert cli.main(["--students", str(students_csv), "--taiga", str(taiga)]) == 1
    assert "issues.csv" in capsys.readouterr().err


def test_missing_student_list_stops_with_message(fake_github, tmp_path, capsys):
    assert cli.main(["--students", str(tmp_path / "yok.csv")]) == 1
    assert "yok.csv" in capsys.readouterr().err


# Wrong arguments stop before any work, with exit code 2 (argparse)


@pytest.mark.parametrize(
    "dates",
    [
        ["--start", "21.09.2026"],  # not YYYY-MM-DD
        ["--start", "2026-10-20", "--end", "2026-10-19"],  # start after end
    ],
)
def test_invalid_dates_stop_with_usage_error(students_csv, dates):
    with pytest.raises(SystemExit) as error:
        cli.main(["--students", str(students_csv), *dates])
    assert error.value.code == 2


# REQ-3.11 — Adjustments and their reasons are shown


def test_adjustments_are_shown_with_reason(fake_github, students_csv, tmp_path, capsys):
    adjustments = tmp_path / "duzeltmeler.csv"
    adjustments.write_text(
        "ad_soyad,puan,gerekce\nTest Öğrenci Bir,+10,Backlog SM tarafından açıldı\n",
        encoding="utf-8",
    )
    assert cli.main(["--students", str(students_csv), "--adjustments", str(adjustments)]) == 0
    assert "Test Öğrenci Bir +10: Backlog SM tarafından açıldı" in capsys.readouterr().out


# REQ-1.7 to REQ-1.9 — Taiga history is downloaded and counted when a Taiga folder is given

STORY_HEADER = "id,ref,owner,assigned_to,status,is_closed,created_date,finished_date\n"


def test_taiga_history_links_a_student_with_no_other_activity(
    fake_github, fake_taiga, students_csv, tmp_path, capsys
):
    # Test Öğrenci Üç has no pull request and owns no Taiga item; only the history shows
    # that they moved a story to Done (the tester case from the acceptance test)
    taiga = write_taiga(tmp_path / "taiga")
    (taiga / "userstories.csv").write_text(
        STORY_HEADER + "7,103,,,Done,True,2026-10-01,2026-10-31\n", encoding="utf-8"
    )
    fake_taiga.histories["/history/userstory/7"] = [
        {
            "user": {"username": "ogrenciuc", "name": "Test Öğrenci Üç"},
            "created_at": "2026-10-31T16:50:51Z",
            "values_diff": {"status": ["Ready for test", "Done"]},
            "comment": "",
        }
    ]
    assert cli.main(["--students", str(students_csv), "--taiga", str(taiga)]) == 0
    captured = capsys.readouterr()
    assert fake_taiga.asked == ["/history/userstory/7"]
    assert "UNMATCHED" not in captured.out
    assert "Downloading Taiga history for 1 items" in captured.err


def test_no_taiga_history_option_skips_login(fake_github, students_csv, tmp_path, monkeypatch):
    def must_not_log_in():
        raise AssertionError("Taiga login should be skipped")

    monkeypatch.setattr(cli, "get_credentials", must_not_log_in)
    taiga = write_taiga(tmp_path / "taiga")
    args = ["--students", str(students_csv), "--taiga", str(taiga), "--no-taiga-history"]
    assert cli.main(args) == 0


def test_taiga_login_error_stops_with_message(
    fake_github, students_csv, tmp_path, monkeypatch, capsys
):
    def wrong_password(username, password):
        raise RuntimeError("Taiga login failed (401): check the username and password")

    monkeypatch.setattr(cli, "get_credentials", lambda: ("hoca", "yanlis"))
    monkeypatch.setattr(cli, "login", wrong_password)
    taiga = write_taiga(tmp_path / "taiga")
    assert cli.main(["--students", str(students_csv), "--taiga", str(taiga)]) == 1
    assert "Taiga login failed" in capsys.readouterr().err
