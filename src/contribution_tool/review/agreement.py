"""How often a model agrees with the instructor's labels (REQ-7.10).

The contributions are read back from the label sheet itself, so the model sees exactly the
text the instructor labelled and no download is needed. Results and disagreements are
saved under data/calibration/, which git ignores.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from contribution_tool.cards import Card
from contribution_tool.evidence import Evidence
from contribution_tool.review.assess import Ask, ModelResponseError
from contribution_tool.review.cache import Cache, assess_cached

DEFAULT_THRESHOLD = 0.80
CANDIDATES = ("gemma4:latest", "qwen3.5:4b", "qwen3.5:latest", "ministral-3:latest")
DEFAULT_RESULTS = Path("data") / "calibration" / "results.json"
DEFAULT_DISAGREEMENTS = Path("data") / "calibration" / "disagreements.csv"

Labels = Mapping[tuple[str, str], str]


@dataclass(frozen=True)
class Disagreement:
    model: str
    evidence_id: str
    item: str
    label: str
    answer: str  # "error" when the model gave no usable answer
    note: str


@dataclass
class Agreement:
    model: str
    compared: int = 0
    agreed: int = 0
    failed: int = 0  # contributions the model could not answer
    by_item: dict[str, list[int]] = field(default_factory=dict)  # item -> [agreed, compared]
    disagreements: list[Disagreement] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.agreed / self.compared if self.compared else 0.0

    def passed(self, threshold: float = DEFAULT_THRESHOLD) -> bool:
        return self.compared > 0 and self.rate >= threshold

    def count(self, item: str, agreed: bool) -> None:
        counts = self.by_item.setdefault(item, [0, 0])
        counts[0] += agreed
        counts[1] += 1
        self.agreed += agreed
        self.compared += 1


def evidence_from_sheet(path: str | Path) -> list[Evidence]:
    """The contributions in the label sheet, from the first row of each."""
    seen: dict[str, Evidence] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            evidence_id = row["evidence_id"]
            if evidence_id in seen:
                continue
            seen[evidence_id] = Evidence(
                kind=row["kind"],
                author="",
                created=None,
                title=row.get("title", ""),
                text=row.get("text", ""),
                url=row.get("url", ""),
                item_id=evidence_id,
            )
    return list(seen.values())


def measure(
    model: str,
    evidence: Iterable[Evidence],
    labels: Labels,
    cards: Mapping[str, Card],
    ask: Ask,
    cache: Cache,
) -> Agreement:
    """Compare the model's answers with every label; unlabelled items are not counted.

    A contribution the model cannot answer counts as a disagreement for all its labels:
    a model that often fails is not a good choice.
    """
    result = Agreement(model)
    for item in evidence:
        card = cards[item.kind]
        wanted = [
            (i.id, labels[(item.item_id, i.id)])
            for i in card.items
            if (item.item_id, i.id) in labels
        ]
        if not wanted:
            continue
        try:
            answers = {r.item_id: r for r in assess_cached(item, card, ask, model, cache).results}
        except ModelResponseError as error:
            result.failed += 1
            for item_id, label in wanted:
                result.count(item_id, False)
                result.disagreements.append(
                    Disagreement(model, item.item_id, item_id, label, "error", str(error))
                )
            continue
        for item_id, label in wanted:
            answer = answers[item_id]
            agreed = answer.answer == label
            result.count(item_id, agreed)
            if not agreed:
                result.disagreements.append(
                    Disagreement(model, item.item_id, item_id, label, answer.answer, answer.note)
                )
    return result


def format_agreement(results: Iterable[Agreement], threshold: float = DEFAULT_THRESHOLD) -> str:
    """A table for the terminal: models from best to worst, then their weakest items."""
    results = sorted(results, key=lambda r: r.rate, reverse=True)
    lines = [f"{'Model':<22} {'Agreed':>9} {'Rate':>6} {'Failed':>6}  Passed (≥ {threshold:.0%})"]
    for r in results:
        passed = "yes" if r.passed(threshold) else "no"
        lines.append(
            f"{r.model:<22} {r.agreed:>4}/{r.compared:<4} {r.rate:>6.0%} {r.failed:>6}  {passed}"
        )
    for r in results:
        weak = sorted(
            (counts[0] / counts[1], item) for item, counts in r.by_item.items() if counts[1]
        )[:3]
        if weak:
            items = ", ".join(f"{item} {rate:.0%}" for rate, item in weak)
            lines.append(f"  {r.model}: weakest items: {items}")
    return "\n".join(lines)


def save_results(
    results: Iterable[Agreement],
    threshold: float = DEFAULT_THRESHOLD,
    path: str | Path = DEFAULT_RESULTS,
    disagreements_path: str | Path = DEFAULT_DISAGREEMENTS,
) -> Path:
    """Save the rates (read later before reports are made) and the disagreements."""
    results = list(results)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "threshold": threshold,
        "models": {
            r.model: {
                "agreed": r.agreed,
                "compared": r.compared,
                "failed": r.failed,
                "rate": round(r.rate, 4),
                "passed": r.passed(threshold),
            }
            for r in results
        },
    }
    path.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    with Path(disagreements_path).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("model", "evidence_id", "item", "label", "answer", "note"))
        for r in results:
            for d in r.disagreements:
                writer.writerow((d.model, d.evidence_id, d.item, d.label, d.answer, d.note))
    return path
