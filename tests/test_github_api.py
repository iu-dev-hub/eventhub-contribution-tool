"""Tests for downloading data from the GitHub GraphQL API (REQ-1.1).

No test connects to GitHub: the API is replaced by fake functions.
"""

import json

import pytest

from contribution_tool.github_api import (
    fetch_discussions,
    fetch_pull_requests,
    graphql_request,
    split_repo,
)


def page(connection, nodes, next_cursor=None):
    info = {"hasNextPage": next_cursor is not None, "endCursor": next_cursor}
    return {"repository": {connection: {"pageInfo": info, "nodes": nodes}}}


class FakeApi:
    """Returns prepared pages and remembers which cursors were asked for."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, query, variables):
        self.calls.append(variables)
        return self.responses.pop(0)


# Pagination — all pages are downloaded


def test_single_page_of_pull_requests():
    api = FakeApi(page("pullRequests", [{"number": 1}]))
    assert fetch_pull_requests("iu-dev-hub/eventhub", api) == [{"number": 1}]
    assert api.calls == [{"owner": "iu-dev-hub", "name": "eventhub", "cursor": None}]


def test_several_pages_of_pull_requests_are_joined():
    api = FakeApi(
        page("pullRequests", [{"number": 1}, {"number": 2}], next_cursor="abc"),
        page("pullRequests", [{"number": 3}]),
    )
    result = fetch_pull_requests("iu-dev-hub/eventhub", api)
    assert [pr["number"] for pr in result] == [1, 2, 3]
    assert api.calls[1]["cursor"] == "abc"


def test_empty_repository_gives_empty_list():
    assert fetch_pull_requests("iu-dev-hub/eventhub", FakeApi(page("pullRequests", []))) == []


def test_more_discussion_comments_are_downloaded():
    first_comments = {
        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
        "nodes": [{"createdAt": "2026-10-01T10:00:00Z"}],
    }
    more_comments = {
        "node": {
            "comments": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [{"createdAt": "2026-10-02T10:00:00Z"}],
            }
        }
    }
    api = FakeApi(page("discussions", [{"id": "D1", "comments": first_comments}]), more_comments)
    discussions = fetch_discussions("iu-dev-hub/eventhub", api)
    assert len(discussions[0]["comments"]["nodes"]) == 2
    assert api.calls[1] == {"id": "D1", "cursor": "c1"}


# Repository name


@pytest.mark.parametrize("repo", ["eventhub", "iu-dev-hub/", "/eventhub", "a/b/c"])
def test_invalid_repository_name_stops_with_error(repo):
    with pytest.raises(ValueError, match="owner/name"):
        split_repo(repo)


# Request to GitHub


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_request_sends_token_and_returns_data(monkeypatch):
    sent = {}

    def fake_urlopen(request, timeout):
        sent["auth"] = request.get_header("Authorization")
        sent["body"] = json.loads(request.data)
        return FakeResponse({"data": {"ok": True}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    send = graphql_request("test-token")
    assert send("query { ok }", {"x": 1}) == {"ok": True}
    assert sent["auth"] == "bearer test-token"
    assert sent["body"] == {"query": "query { ok }", "variables": {"x": 1}}


def test_api_error_stops_with_message(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"errors": [{"message": "Bad credentials"}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="Bad credentials"):
        graphql_request("wrong-token")("query { ok }", {})
