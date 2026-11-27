"""How often a model agrees with the instructor's labels (REQ-7.10).

The contributions are read back from the label sheet itself, so the model sees exactly the
text the instructor labelled and no download is needed. Results and disagreements are
saved under data/calibration/, which git ignores.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from contribution_tool.cards import Card
from contribution_tool.evidence import Evidence
from contribution_tool.review.assess import ModelResponseError
from contribution_tool.review.vote import UNCERTAIN, Judge

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
    answer: str  # "error" when no usable answer, "uncertain" when a vote had no majority
    note: str


@dataclass
class Agreement:
    model: str
    compared: int = 0
    agreed: int = 0
    failed: int = 0  # contributions the model could not answer
    uncertain: int = 0  # labels where the models of a vote did not agree
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
    name: str,
    evidence: Iterable[Evidence],
    labels: Labels,
    cards: Mapping[str, Card],
    judge: Judge,
) -> Agreement:
    """Compare the answers of one model (or one vote) with every label.

    Unlabelled items are not counted. A contribution that gets no usable answer, and an
    uncertain vote, count as disagreements: a method that often fails is not a good choice.
    """
    result = Agreement(name)
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
            answers = {r.item_id: r for r in judge(item, card).results}
        except ModelResponseError as error:
            result.failed += 1
            for item_id, label in wanted:
                result.count(item_id, False)
                result.disagreements.append(
                    Disagreement(name, item.item_id, item_id, label, "error", str(error))
                )
            continue
        for item_id, label in wanted:
            answer = answers[item_id]
            agreed = answer.answer == label
            result.count(item_id, agreed)
            result.uncertain += answer.answer == UNCERTAIN
            if not agreed:
                result.disagreements.append(
                    Disagreement(name, item.item_id, item_id, label, answer.answer, answer.note)
                )
    return result


def format_agreement(results: Iterable[Agreement], threshold: float = DEFAULT_THRESHOLD) -> str:
    """A table for the terminal: best first, then the weakest items of each."""
    results = sorted(results, key=lambda r: r.rate, reverse=True)
    width = max([len("Model")] + [len(r.model) for r in results])
    lines = [
        f"{'Model':<{width}} {'Agreed':>9} {'Rate':>5} {'Failed':>6} {'Unsure':>6}"
        f"  Passed (≥ {threshold:.0%})"
    ]
    for r in results:
        passed = "yes" if r.passed(threshold) else "no"
        lines.append(
            f"{r.model:<{width}} {r.agreed:>4}/{r.compared:<4} {r.rate:>5.0%} {r.failed:>6}"
            f" {r.uncertain:>6}  {passed}"
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
                "uncertain": r.uncertain,
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


def calibrated(models: Sequence[str], path: str | Path = DEFAULT_RESULTS) -> tuple[str, float]:
    """The method's name and agreement rate, if it passed calibration (REQ-7.10).

    One model: that model must have passed. Several models: their vote must have passed.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError(
            f"No calibration results in {path}: run 'contribution-review calibrate --vote' first"
        ) from None
    entries = data.get("models", {})
    for name, entry in entries.items():
        voters = name.removeprefix("vote:").split("+") if name.startswith("vote:") else [name]
        if set(voters) == set(models) and len(voters) == len(models) and entry.get("passed"):
            return name, float(entry["rate"])
    method = models[0] if len(models) == 1 else "the vote of " + ", ".join(models)
    raise ValueError(
        f"{method} has not passed calibration (threshold {data.get('threshold')}), "
        "so no reports are made (REQ-7.10)"
    )
