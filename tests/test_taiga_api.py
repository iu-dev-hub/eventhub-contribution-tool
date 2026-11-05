"""Tests for downloading change history from the Taiga API (REQ-1.7, REQ-6.4).

No test connects to Taiga: the API is replaced by fake functions.
"""

import io
import json
import urllib.error

import pytest

from contribution_tool.taiga_api import (
    fetch_histories,
    get_credentials,
    ids_from_rows,
    login,
    taiga_request,
)


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def no_prompt(text):
    raise AssertionError("the password should not be asked")


# REQ-6.4 — Credentials: username from the environment, password from it or a prompt


def test_credentials_from_environment():
    environ = {
        "CONTRIBUTION_TOOL_TAIGA_USERNAME": "hoca",
        "CONTRIBUTION_TOOL_TAIGA_PASSWORD": "gizli",
    }
    assert get_credentials(environ, prompt=no_prompt) == ("hoca", "gizli")


def test_password_is_asked_when_not_in_environment():
    environ = {"CONTRIBUTION_TOOL_TAIGA_USERNAME": "hoca"}
    assert get_credentials(environ, prompt=lambda text: "gizli") == ("hoca", "gizli")


def test_missing_username_stops_with_message():
    with pytest.raises(RuntimeError, match="CONTRIBUTION_TOOL_TAIGA_USERNAME"):
        get_credentials({}, prompt=no_prompt)


def test_empty_password_stops_with_message():
    environ = {"CONTRIBUTION_TOOL_TAIGA_USERNAME": "hoca"}
    with pytest.raises(RuntimeError, match="password is empty"):
        get_credentials(environ, prompt=lambda text: "")


# Login


def test_login_sends_credentials_and_returns_token(monkeypatch):
    sent = {}

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["body"] = json.loads(request.data)
        return FakeResponse({"auth_token": "test-token", "refresh": "x"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert login("hoca", "gizli") == "test-token"
    assert sent["url"].endswith("/auth")
    assert sent["body"] == {"type": "normal", "username": "hoca", "password": "gizli"}


def test_wrong_password_stops_with_message(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="login failed"):
        login("hoca", "yanlis")


def test_request_sends_token_and_disables_pagination(monkeypatch):
    sent = {}

    def fake_urlopen(request, timeout):
        sent["auth"] = request.get_header("Authorization")
        sent["pagination"] = request.get_header("X-disable-pagination")
        return FakeResponse([{"id": "h1"}])

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert taiga_request("test-token")("/history/userstory/1") == [{"id": "h1"}]
    assert sent["auth"] == "Bearer test-token"
    assert sent["pagination"] == "True"


# REQ-1.7 — History is downloaded for each item in the CSV export


def test_ids_are_read_from_csv_rows():
    assert ids_from_rows([{"id": "101", "ref": "5"}, {"id": "102", "ref": "6"}]) == [101, 102]


def test_csv_without_id_column_stops_with_error():
    with pytest.raises(ValueError, match="'id'"):
        ids_from_rows([{"ref": "5"}])


def test_empty_csv_gives_no_ids():
    assert ids_from_rows([]) == []


def test_history_is_downloaded_for_each_item():
    asked = []

    def fake_send(path):
        asked.append(path)
        return [{"path": path}]

    histories = fetch_histories("userstory", [101, 102], fake_send)
    assert asked == ["/history/userstory/101", "/history/userstory/102"]
    assert histories == [[{"path": "/history/userstory/101"}], [{"path": "/history/userstory/102"}]]


def test_unknown_item_kind_stops_with_error():
    with pytest.raises(ValueError, match="epic"):
        fetch_histories("epic", [1], lambda path: [])
