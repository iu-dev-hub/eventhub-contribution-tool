"""Saved assessments, so an unchanged contribution is not assessed again (REQ-7.5).

Each assessment is one JSON file under data/cache/. The file name comes from everything
the answer depends on: the contribution's id and text, the card, the model and the
instructions given to the model. If any of these changes, the file name changes too.

The cache holds notes about students' work: it lives in data/, which git ignores.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from contribution_tool.cards import Card
from contribution_tool.evidence import Evidence
from contribution_tool.review import assess as assess_module
from contribution_tool.review.assess import Ask, Assessment, ItemResult, assess, content_hash

DEFAULT_CACHE_DIR = Path("data") / "cache"
FORMAT = 1  # raise when the file layout changes; older files are then ignored


def prompt_fingerprint() -> str:
    """Changes when the instructions to the model change."""
    return hashlib.sha256(assess_module.SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12]


def cache_key(evidence: Evidence, card: Card, model: str) -> str:
    parts = (evidence.item_id, content_hash(evidence), card.fingerprint, model)
    text = "\n".join((*parts, prompt_fingerprint()))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


class Cache:
    def __init__(self, folder: str | Path = DEFAULT_CACHE_DIR) -> None:
        self.folder = Path(folder)
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.folder / f"{key}.json"

    def get(self, evidence: Evidence, card: Card, model: str) -> Assessment | None:
        """The saved assessment, or None if there is none or it cannot be read."""
        path = self._path(cache_key(evidence, card, model))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("format") != FORMAT:
                return None
            return _from_dict(data["assessment"])
        except (OSError, ValueError, KeyError, TypeError):
            return None  # missing or damaged: assess again

    def put(self, evidence: Evidence, card: Card, assessment: Assessment) -> None:
        """Save one assessment; a half-written file is never left behind."""
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self._path(cache_key(evidence, card, assessment.model))
        data = {"format": FORMAT, "assessment": _to_dict(assessment)}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, path)


def assess_cached(evidence: Evidence, card: Card, ask: Ask, model: str, cache: Cache) -> Assessment:
    """Use the saved assessment if nothing changed; otherwise ask the model and save."""
    saved = cache.get(evidence, card, model)
    if saved is not None:
        cache.hits += 1
        return saved
    cache.misses += 1
    result = assess(evidence, card, ask, model)
    cache.put(evidence, card, result)
    return result


def _to_dict(assessment: Assessment) -> dict:
    return {
        "evidence_id": assessment.evidence_id,
        "kind": assessment.kind,
        "author": assessment.author,
        "results": [[r.item_id, r.answer, r.note] for r in assessment.results],
        "suspicious": assessment.suspicious,
        "empty": assessment.empty,
        "content_hash": assessment.content_hash,
        "card_fingerprint": assessment.card_fingerprint,
        "model": assessment.model,
    }


def _from_dict(data: dict) -> Assessment:
    results = tuple(ItemResult(*entry) for entry in data["results"])
    return Assessment(
        evidence_id=data["evidence_id"],
        kind=data["kind"],
        author=data["author"],
        results=results,
        suspicious=bool(data["suspicious"]),
        empty=bool(data["empty"]),
        content_hash=data["content_hash"],
        card_fingerprint=data["card_fingerprint"],
        model=data["model"],
    )
