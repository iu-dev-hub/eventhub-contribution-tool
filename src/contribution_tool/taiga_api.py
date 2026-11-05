"""Downloading change history from the Taiga API (REQ-1.7, REQ-6.4).

The project is private, so the tool logs in with the instructor's Taiga account at the
start of each run. The password is never stored; the access token is kept in memory only.
"""

from __future__ import annotations

import getpass
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from typing import Any

API_URL = "https://api.taiga.io/api/v1"
USERNAME_VARIABLE = "CONTRIBUTION_TOOL_TAIGA_USERNAME"
PASSWORD_VARIABLE = "CONTRIBUTION_TOOL_TAIGA_PASSWORD"
KINDS = ("userstory", "task", "issue")

Send = Callable[[str], Any]


def get_credentials(
    environ: Mapping[str, str] = os.environ, prompt: Callable[[str], str] = getpass.getpass
) -> tuple[str, str]:
    """Taiga username from the environment; password from the environment or a prompt."""
    username = environ.get(USERNAME_VARIABLE, "").strip()
    if not username:
        raise RuntimeError(f"{USERNAME_VARIABLE} is not set (your Taiga username)")
    password = environ.get(PASSWORD_VARIABLE, "") or prompt(f"Taiga password for {username}: ")
    if not password:
        raise RuntimeError("Taiga password is empty")
    return username, password


def login(username: str, password: str) -> str:
    """Log in to Taiga and return an access token (valid for about one day)."""
    body = json.dumps({"type": "normal", "username": username, "password": password}).encode()
    request = urllib.request.Request(
        f"{API_URL}/auth", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())["auth_token"]
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Taiga login failed ({error.code}): check the username and password"
        ) from None


def taiga_request(token: str) -> Send:
    """Return a function that sends one GET request to the Taiga API with the token."""

    def send(path: str) -> Any:
        request = urllib.request.Request(
            f"{API_URL}{path}",
            headers={"Authorization": f"Bearer {token}", "x-disable-pagination": "True"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())

    return send


def ids_from_rows(rows: Iterable[Mapping[str, str]]) -> list[int]:
    """The Taiga ids of the items in a CSV export (REQ-1.7)."""
    rows = list(rows)
    if rows and "id" not in rows[0]:
        raise ValueError("Taiga CSV export has no 'id' column")
    return [int(row["id"]) for row in rows if row.get("id")]


def fetch_histories(kind: str, ids: Iterable[int], send: Send) -> list[list[dict[str, Any]]]:
    """Download the change history of each item: one list of entries per item."""
    if kind not in KINDS:
        raise ValueError(f"Unknown Taiga item kind '{kind}', expected one of {KINDS}")
    return [send(f"/history/{kind}/{item_id}") for item_id in ids]
