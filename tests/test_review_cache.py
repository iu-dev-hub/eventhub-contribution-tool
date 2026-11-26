"""Tests for saved assessments (REQ-7.5).

The model is a fake that counts its calls; every test uses its own temporary folder.
"""

import dataclasses

import pytest

from contribution_tool.cards import Card, CardItem
from contribution_tool.evidence import Evidence
from contribution_tool.review import assess as assess_module
from contribution_tool.review.cache import Cache, assess_cached

CARD = Card(
    kind="code_review",
    title="Kod incelemesi",
    items=(CardItem("review.finding", "Somut bulgu var mı?", "kaynak", "öneri"),),
    fingerprint="card123",
)

ANSWER = {
    "review.finding": {"answer": "met", "note": "BR-3.3 ile gerekçeli bulgu var."},
    "suspicious": False,
}


class CountingModel:
    def __init__(self):
        self.calls = 0

    def __call__(self, system, prompt, schema):
        self.calls += 1
        return ANSWER


def review(text="zorunlu: BR-3.3'e göre satış 60 dk önce kapanmalı", **values):
    data = {
        "kind": "code_review",
        "author": "ogrenciiki",
        "created": None,
        "title": "Review on PR #12",
        "text": text,
        "url": "https://example.org/pull/12",
        "item_id": "github:review:12",
    }
    data.update(values)
    return Evidence(**data)


@pytest.fixture
def cache(tmp_path):
    return Cache(tmp_path / "cache")


# REQ-7.5 — Unchanged contributions are not assessed again


def test_second_run_uses_the_saved_assessment(cache):
    model = CountingModel()
    first = assess_cached(review(), CARD, model, "m", cache)
    second = assess_cached(review(), CARD, model, "m", cache)
    assert model.calls == 1
    assert second == first
    assert (cache.hits, cache.misses) == (1, 1)


def test_saved_assessment_survives_a_new_run(cache):
    model = CountingModel()
    first = assess_cached(review(), CARD, model, "m", cache)
    again = Cache(cache.folder)  # as if the program was started again
    assert assess_cached(review(), CARD, model, "m", again) == first
    assert model.calls == 1


@pytest.mark.parametrize(
    ("evidence", "card", "model_name"),
    [
        (review(text="zorunlu: BR-3.3 ihlali. Düzeltildi."), CARD, "m"),
        (review(title="Yeni başlık"), CARD, "m"),
        (review(), dataclasses.replace(CARD, fingerprint="card456"), "m"),
        (review(), CARD, "another-model"),
    ],
    ids=["text", "title", "card", "model"],
)
def test_any_change_means_a_new_assessment(cache, evidence, card, model_name):
    model = CountingModel()
    assess_cached(review(), CARD, model, "m", cache)
    assess_cached(evidence, card, model, model_name, cache)
    assert model.calls == 2


def test_new_instructions_to_the_model_mean_a_new_assessment(cache, monkeypatch):
    model = CountingModel()
    assess_cached(review(), CARD, model, "m", cache)
    monkeypatch.setattr(assess_module, "SYSTEM_PROMPT", assess_module.SYSTEM_PROMPT + " Kısa yaz.")
    assess_cached(review(), CARD, model, "m", cache)
    assert model.calls == 2


def test_damaged_file_is_assessed_again(cache):
    model = CountingModel()
    assess_cached(review(), CARD, model, "m", cache)
    for path in cache.folder.glob("*.json"):
        path.write_text("{ yarım", encoding="utf-8")
    assert assess_cached(review(), CARD, model, "m", cache).results[0].answer == "met"
    assert model.calls == 2


def test_file_of_an_older_format_is_ignored(cache):
    model = CountingModel()
    assess_cached(review(), CARD, model, "m", cache)
    for path in cache.folder.glob("*.json"):
        path.write_text(path.read_text(encoding="utf-8").replace('"format": 1', '"format": 0'))
    assess_cached(review(), CARD, model, "m", cache)
    assert model.calls == 2


def test_nothing_is_saved_when_the_model_fails(cache):
    def broken(system, prompt, schema):
        return {"suspicious": False}  # no answer for the item

    with pytest.raises(assess_module.ModelResponseError):
        assess_cached(review(), CARD, broken, "m", cache)
    assert not cache.folder.exists() or not any(cache.folder.iterdir())


def test_turkish_notes_are_kept_readable(cache):
    assess_cached(review(), CARD, CountingModel(), "m", cache)
    (path,) = cache.folder.glob("*.json")
    assert "gerekçeli" in path.read_text(encoding="utf-8")
