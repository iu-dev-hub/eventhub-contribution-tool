"""The instructor's labels for checking the model (REQ-7.10).

A fixed sample of real contributions is written to a CSV file, one row per card item.
The instructor fills in the label column; the model's answers are later compared with it.

The file contains students' texts: it lives in data/, which git ignores.
"""

from __future__ import annotations

import csv
import random
from collections.abc import Iterable, Mapping
from pathlib import Path

from contribution_tool.cards import Card
from contribution_tool.evidence import KINDS, Evidence
from contribution_tool.review.assess import (
    MET,
    NOT_APPLICABLE,
    NOT_MET,
    allowed_answers,
    shown_text,
)

DEFAULT_SHEET = Path("data") / "calibration" / "labels.csv"
PER_KIND = 5
SEED = 42
COLUMNS = ("evidence_id", "kind", "item", "question", "answers", "label", "title", "text", "url")

# What the instructor may type in the label column
LABELS = {
    "e": MET,
    "evet": MET,
    MET: MET,
    "h": NOT_MET,
    "hayır": NOT_MET,
    "hayir": NOT_MET,
    NOT_MET: NOT_MET,
    "u": NOT_APPLICABLE,
    "uygulanamaz": NOT_APPLICABLE,
    NOT_APPLICABLE: NOT_APPLICABLE,
}
SHORT = {MET: "e", NOT_MET: "h", NOT_APPLICABLE: "u"}


class LabelError(ValueError):
    """A label in the instructor's file cannot be used."""


def choose_sample(
    evidence: Iterable[Evidence], per_kind: int = PER_KIND, seed: int = SEED
) -> list[Evidence]:
    """The same contributions every time for the same data: a few of each kind.

    Empty texts are left out: they are never sent to the model.
    """
    by_kind: dict[str, list[Evidence]] = {kind: [] for kind in KINDS}
    for item in evidence:
        if item.text.strip():
            by_kind[item.kind].append(item)
    chosen: list[Evidence] = []
    for kind in KINDS:
        items = sorted(by_kind[kind], key=lambda e: e.item_id)
        chosen += random.Random(f"{seed}:{kind}").sample(items, min(per_kind, len(items)))
    return chosen


def write_label_sheet(
    sample: Iterable[Evidence], cards: Mapping[str, Card], path: str | Path = DEFAULT_SHEET
) -> Path:
    """One row per card item; the text is shown on the first row of each contribution.

    An existing file is never overwritten: it may already hold the instructor's labels.
    """
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} already exists; it may hold your labels")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        for evidence in sample:
            card = cards[evidence.kind]
            for number, item in enumerate(card.items):
                first = number == 0
                writer.writerow(
                    (
                        evidence.item_id,
                        evidence.kind,
                        item.id,
                        item.question,
                        " / ".join(SHORT[a] for a in allowed_answers(item)),
                        "",
                        evidence.title if first else "",
                        shown_text(evidence) if first else "",
                        evidence.url if first else "",
                    )
                )
    return path


def load_labels(path: str | Path, cards: Mapping[str, Card]) -> dict[tuple[str, str], str]:
    """The instructor's labels by (evidence id, item id); empty labels are skipped."""
    labels: dict[tuple[str, str], str] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        for line, row in enumerate(csv.DictReader(file), start=2):
            raw = (row.get("label") or "").strip().lower()
            if not raw:
                continue
            card = cards.get(row.get("kind", ""))
            item = next((i for i in card.items if i.id == row.get("item")), None) if card else None
            if item is None:
                raise LabelError(f"Line {line}: unknown item '{row.get('item')}'")
            answer = LABELS.get(raw)
            if answer is None:
                raise LabelError(f"Line {line}: '{raw}' is not a label; use e, h or u")
            if answer not in allowed_answers(item):
                raise LabelError(f"Line {line}: '{item.id}' cannot be 'uygulanamaz'")
            labels[(row["evidence_id"], item.id)] = answer
    return labels
