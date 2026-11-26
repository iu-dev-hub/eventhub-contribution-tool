"""Majority vote of several models (REQ-7.11).

Each item gets the answer most models gave. Without a majority (e.g. three different
answers, or one against one when a model failed) the item is "uncertain": it is not
counted in a student's rates and is listed for the instructor instead. A contribution is
suspicious if any model found it suspicious.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence

from contribution_tool.cards import Card
from contribution_tool.evidence import Evidence
from contribution_tool.review.assess import Assessment, ItemResult, ModelResponseError

UNCERTAIN = "uncertain"
VOTERS = ("ministral-3:latest", "qwen3.5:latest", "gemma4:latest")  # passed calibration

# Assesses one contribution with its card: one model, or a vote of several
Judge = Callable[[Evidence, Card], Assessment]


def vote(assessments: Sequence[Assessment], name: str) -> Assessment:
    """One assessment from several: the majority answer for each item."""
    if not assessments:
        raise ValueError("Nothing to vote on")
    first = assessments[0]
    by_model = [{r.item_id: r for r in a.results} for a in assessments]
    results = []
    for item in first.results:
        answers = [results_of[item.item_id] for results_of in by_model]
        answer, votes = Counter(r.answer for r in answers).most_common(1)[0]
        if votes * 2 <= len(answers):  # no strict majority
            note = "Modeller anlaşamadı: " + ", ".join(r.answer for r in answers)
            results.append(ItemResult(item.item_id, UNCERTAIN, note))
        else:
            note = next(r.note for r in answers if r.answer == answer)
            results.append(ItemResult(item.item_id, answer, note))
    return Assessment(
        evidence_id=first.evidence_id,
        kind=first.kind,
        author=first.author,
        results=tuple(results),
        suspicious=any(a.suspicious for a in assessments),
        empty=first.empty,
        content_hash=first.content_hash,
        card_fingerprint=first.card_fingerprint,
        model=name,
    )


def majority(judges: Sequence[Judge], name: str) -> Judge:
    """A judge that asks every model and takes the vote; failed models are left out."""

    def judge(evidence: Evidence, card: Card) -> Assessment:
        found = []
        for one in judges:
            try:
                found.append(one(evidence, card))
            except ModelResponseError:
                continue
        if not found:
            raise ModelResponseError("No model gave a usable answer")
        return vote(found, name)

    return judge


def run_models(
    evidence: Sequence[Evidence],
    cards: Mapping[str, Card],
    judges: Mapping[str, Judge],
    progress: Callable[[str], None] = lambda text: None,
) -> dict[str, int]:
    """Run each model over every contribution, one model after another.

    One model at a time: the GPU loads each model once instead of switching models for every
    contribution. The judges save every answer, so the vote is counted later without asking
    any model again. Returns the number of contributions each model could not answer.
    """
    failed = {}
    for model, judge in judges.items():
        failed[model] = 0
        for number, item in enumerate(evidence, start=1):
            try:
                judge(item, cards[item.kind])
            except ModelResponseError:
                failed[model] += 1
            progress(f"{model}: {number}/{len(evidence)}")
    return failed
