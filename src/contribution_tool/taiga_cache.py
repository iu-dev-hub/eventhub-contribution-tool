"""Saved Taiga change histories, so unchanged items are not downloaded again (REQ-1.10).

Taiga changes an item's modified_date whenever the item changes, including when a comment
is added. A saved history is used only if the item's modified_date in the new CSV export is
the same as when it was saved. Items without a modified_date are always downloaded.

The histories hold comments and names: they live in data/, which git ignores.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from contribution_tool.taiga_api import Send, fetch_histories

DEFAULT_HISTORY_DIR = Path("data") / "cache" / "taiga-history"
FORMAT = 1

History = list[dict[str, Any]]


class HistoryCache:
    def __init__(self, folder: str | Path = DEFAULT_HISTORY_DIR) -> None:
        self.folder = Path(folder)
        self.downloaded = 0
        self.reused = 0

    def _path(self, kind: str, item_id: int) -> Path:
        return self.folder / f"{kind}-{item_id}.json"

    def get(self, kind: str, item_id: int, modified: str) -> History | None:
        """The saved history if the item has not changed since; otherwise None."""
        if not modified:
            return None
        try:
            data = json.loads(self._path(kind, item_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # missing or damaged: download again
        if data.get("format") != FORMAT or data.get("modified_date") != modified:
            return None
        history = data.get("history")
        return history if isinstance(history, list) else None

    def put(self, kind: str, item_id: int, modified: str, history: History) -> None:
        """Save one history; without a modified_date it could never be checked, so skip it."""
        if not modified:
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self._path(kind, item_id)
        data = {"format": FORMAT, "modified_date": modified, "history": history}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)


def cached_histories(
    kind: str,
    rows: Iterable[Mapping[str, str]],
    cache: HistoryCache,
    connect: Callable[[], Send],
) -> list[History]:
    """One history per CSV row, in the same order; Taiga is asked only for changed items.

    connect() logs in to Taiga; it is called only when something must be downloaded.
    """
    rows = list(rows)
    if rows and "id" not in rows[0]:
        raise ValueError("Taiga CSV export has no 'id' column")
    histories: list[History] = []
    for row in rows:
        if not row.get("id"):
            continue
        item_id = int(row["id"])
        modified = (row.get("modified_date") or "").strip()
        history = cache.get(kind, item_id, modified)
        if history is None:
            (history,) = fetch_histories(kind, [item_id], connect())
            cache.put(kind, item_id, modified, history)
            cache.downloaded += 1
        else:
            cache.reused += 1
        histories.append(history)
    return histories
