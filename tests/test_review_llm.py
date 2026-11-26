"""Tests for asking a local Ollama model (REQ-7.3). No test needs Ollama."""

import io
import json
import urllib.error

import pytest

from contribution_tool.review.llm import ollama


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_request_is_local_repeatable_and_asks_for_json(monkeypatch):
    sent = {}

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["body"] = json.loads(request.data)
        return FakeResponse({"message": {"content": '{"x": {"answer": "met"}}'}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    answer = ollama("test-model")("sistem", "istem", {"type": "object"})
    assert answer == {"x": {"answer": "met"}}
    assert sent["url"] == "http://localhost:11434/api/chat"
    body = sent["body"]
    assert body["model"] == "test-model"
    assert body["format"] == {"type": "object"}
    assert body["options"] == {"temperature": 0, "seed": 42, "num_ctx": 4096}
    assert body["think"] is False
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_missing_model_says_how_to_install_it(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="ollama pull test-model"):
        ollama("test-model")("s", "p", {})


def test_ollama_not_running_says_how_to_start_it(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="ollama serve"):
        ollama("test-model")("s", "p", {})


def test_answer_that_is_not_json_stops_with_error(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse({"message": {"content": "tamam, hepsi met"}}),
    )
    with pytest.raises(RuntimeError, match="not JSON.*tamam, hepsi met"):
        ollama("test-model")("s", "p", {})


# Thinking models: found in the acceptance test with qwen3.5:9b, which thought for
# 14,378 characters, filled the context and wrote no answer (done_reason=length)


def test_cut_answer_says_the_context_was_too_small(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            {"message": {"content": "", "thinking": "..."}, "done_reason": "length"}
        ),
    )
    with pytest.raises(RuntimeError, match="context too small"):
        ollama("test-model")("s", "p", {})


def test_model_without_thinking_mode_is_asked_again_without_the_setting(monkeypatch):
    sent = []

    def fake_urlopen(request, timeout):
        body = json.loads(request.data)
        sent.append("think" in body)
        if "think" in body:
            error = b'{"error":"\\"test-model\\" does not support thinking"}'
            raise urllib.error.HTTPError(request.full_url, 400, "Bad", {}, io.BytesIO(error))
        return FakeResponse({"message": {"content": '{"ok": true}'}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    ask = ollama("test-model")
    assert ask("s", "p", {}) == {"ok": True}
    assert ask("s", "p", {}) == {"ok": True}
    assert sent == [True, False, False]  # the second question does not try again


def test_other_bad_request_is_not_retried(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(1)
        error = b'{"error":"invalid format schema"}'
        raise urllib.error.HTTPError(request.full_url, 400, "Bad", {}, io.BytesIO(error))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="invalid format schema"):
        ollama("test-model")("s", "p", {})
    assert calls == [1]
