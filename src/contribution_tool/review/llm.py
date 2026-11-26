"""Asking a local Ollama model, with JSON output (REQ-7.3)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

from contribution_tool.review.assess import Ask

OLLAMA_URL = "http://localhost:11434"
CONTEXT_TOKENS = 4096


def ollama(model: str, url: str = OLLAMA_URL, context: int = CONTEXT_TOKENS) -> Ask:
    """Return a function that asks the model and returns its JSON answer.

    Temperature 0 and a fixed seed make answers repeatable. Thinking is turned off:
    a thinking model used the whole context for thinking and wrote no answer. The model
    runs on this computer; nothing is sent over the internet.
    """
    send_think = True  # becomes False if the model does not accept the setting

    def ask(system: str, prompt: str, schema: dict[str, Any]) -> Mapping[str, Any]:
        nonlocal send_think
        body = {
            "model": model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "seed": 42, "num_ctx": context},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        if send_think:
            body["think"] = False
        try:
            reply = _post(f"{url}/api/chat", body)
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", "replace")
            if error.code == 400 and "think" in message and send_think:
                send_think = False  # a model without a thinking mode refused the setting
                return ask(system, prompt, schema)
            if error.code == 404:
                raise RuntimeError(
                    f"Model '{model}' is not installed. Run: ollama pull {model}"
                ) from None
            raise RuntimeError(f"Ollama error {error.code}: {message[:200]}") from None
        except urllib.error.URLError:
            raise RuntimeError(
                f"Ollama is not running at {url}. Start it with: ollama serve"
            ) from None

        content = (reply.get("message") or {}).get("content") or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            reason = reply.get("done_reason", "unknown")
            hint = " (the answer was cut: context too small)" if reason == "length" else ""
            raise RuntimeError(
                f"Ollama returned an answer that is not JSON{hint}. "
                f"done_reason={reason}, start of answer: {content[:120]!r}"
            ) from None

    return ask


def _post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read())
