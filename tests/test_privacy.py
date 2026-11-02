"""Tests for privacy and security rules (REQ-6.2)."""

import re
from pathlib import Path

import pytest

from contribution_tool.github_api import get_token

SOURCE = Path(__file__).parent.parent / "src"


# REQ-6.2 — The GitHub token is read from the environment, not from code


def test_token_is_read_from_environment():
    assert get_token({"GITHUB_TOKEN": "test-token"}) == "test-token"


@pytest.mark.parametrize("environ", [{}, {"GITHUB_TOKEN": ""}, {"GITHUB_TOKEN": "   "}])
def test_missing_token_stops_with_instructions(environ):
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        get_token(environ)


def test_no_token_is_written_in_source_code():
    # GitHub tokens start with ghp_ (classic) or github_pat_ (fine-grained)
    pattern = re.compile(r"(ghp_|github_pat_)[A-Za-z0-9_]{10,}")
    leaks = [str(path) for path in SOURCE.rglob("*.py") if pattern.search(path.read_text())]
    assert leaks == []
