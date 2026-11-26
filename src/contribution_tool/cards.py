"""Expectation cards: what is expected of each kind of contribution (REQ-7.2)."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

from contribution_tool.evidence import KINDS

CARDS_DIR = Path(__file__).resolve().parents[2] / "cards"
ITEM_FIELDS = ("id", "question", "source", "tip")


@dataclass(frozen=True)
class CardItem:
    id: str
    question: str
    source: str
    tip: str
    industry: bool = False  # True when the item comes from industry practice, not EventHub
    not_applicable: bool = False  # True when the question allows "not applicable"


@dataclass(frozen=True)
class Card:
    kind: str
    title: str
    items: tuple[CardItem, ...]
    fingerprint: str  # changes whenever the card file changes (REQ-7.5)


def load_card(path: str | Path) -> Card:
    """Read and check one card file."""
    path = Path(path)
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode("utf-8"))
    name = path.name

    kind = data.get("kind", "")
    if kind not in KINDS:
        raise ValueError(f"{name}: unknown kind '{kind}', expected one of {KINDS}")
    if not str(data.get("title", "")).strip():
        raise ValueError(f"{name}: 'title' is empty")

    items = []
    seen = set()
    for number, item in enumerate(data.get("items", []), 1):
        missing = [f for f in ITEM_FIELDS if not str(item.get(f, "")).strip()]
        if missing:
            raise ValueError(f"{name}: item {number} is missing {', '.join(missing)}")
        if item["id"] in seen:
            raise ValueError(f"{name}: item id '{item['id']}' is used twice")
        seen.add(item["id"])
        items.append(
            CardItem(
                id=item["id"].strip(),
                question=item["question"].strip(),
                source=item["source"].strip(),
                tip=item["tip"].strip(),
                industry=bool(item.get("industry", False)),
                not_applicable=bool(item.get("not_applicable", False)),
            )
        )
    if not items:
        raise ValueError(f"{name}: a card needs at least one item")

    fingerprint = hashlib.sha256(raw).hexdigest()[:12]
    return Card(kind, data["title"].strip(), tuple(items), fingerprint)


def load_cards(folder: str | Path = CARDS_DIR) -> dict[str, Card]:
    """Read every card in the folder; each contribution kind must have exactly one card."""
    cards: dict[str, Card] = {}
    for path in sorted(Path(folder).glob("*.toml")):
        card = load_card(path)
        if card.kind in cards:
            raise ValueError(f"{path.name}: a card for '{card.kind}' already exists")
        cards[card.kind] = card
    missing = [kind for kind in KINDS if kind not in cards]
    if missing:
        raise ValueError(f"No card for: {', '.join(missing)}")
    return cards
