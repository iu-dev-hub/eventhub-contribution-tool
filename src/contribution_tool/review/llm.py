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

    Temperature 0 and a fixed seed make answers repeatable. The model runs on this
    computer; nothing is sent over the internet.
    """

    def ask(system: str, prompt: str, schema: dict[str, Any]) -> Mapping[str, Any]:
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
        request = urllib.request.Request(
            f"{url}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                reply = json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise RuntimeError(
                    f"Model '{model}' is not installed. Run: ollama pull {model}"
                ) from None
            raise RuntimeError(f"Ollama error {error.code}") from None
        except urllib.error.URLError:
            raise RuntimeError(
                f"Ollama is not running at {url}. Start it with: ollama serve"
            ) from None
        try:
            return json.loads(reply["message"]["content"])
        except (KeyError, json.JSONDecodeError):
            raise RuntimeError("Ollama returned an answer that is not JSON") from None

    return ask
