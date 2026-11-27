"""One private Markdown report per student (REQ-7.6 to REQ-7.9).

Everything here is counted in code from the saved assessments: the model only answered
the card questions. The tips come from the cards, never from the model (REQ-7.8). Each
student's file holds only that student's contributions (REQ-7.9); the summary for the
instructor is a separate file. All files live in data/reports/, which git ignores.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from contribution_tool.cards import Card, CardItem
from contribution_tool.evidence import Evidence
from contribution_tool.matching import MatchResult, normalize_name
from contribution_tool.review.assess import MET, NOT_MET, Assessment
from contribution_tool.review.vote import UNCERTAIN

DEFAULT_REPORT_DIR = Path("data") / "reports"
SUMMARY_FILE = "_ogretim-uyesi-ozet.md"  # instructor only: holds every student's name
GITHUB_KINDS = frozenset({"pull_request", "code_review", "discussion_post"})
GAP_BELOW = 0.75  # items met less often than this are shown as gaps
MAX_GAPS = 5
MIN_FOR_STRENGTH = 2  # an item is a strength only if met in at least this many contributions
MAX_NOTE = 200


@dataclass(frozen=True)
class Period:
    """A role period, e.g. D1 from the first week to the role change (REQ-7.7)."""

    name: str
    start: date
    end: date

    def contains(self, day: date | None) -> bool:
        return day is not None and self.start <= day <= self.end


def parse_period(text: str) -> Period:
    """'D1=2026-09-29..2026-11-02' -> Period."""
    try:
        name, dates = text.split("=", 1)
        start, end = (date.fromisoformat(part.strip()) for part in dates.split(".."))
    except ValueError:
        raise ValueError(f"Period '{text}' must look like D1=2026-09-29..2026-11-02") from None
    if start > end:
        raise ValueError(f"Period '{text}' ends before it starts")
    return Period(name.strip(), start, end)


@dataclass
class ItemCount:
    met: int = 0
    not_met: int = 0
    example: tuple[Evidence, str] | None = None  # a contribution that did not meet it

    @property
    def answered(self) -> int:
        return self.met + self.not_met

    @property
    def rate(self) -> float | None:
        return self.met / self.answered if self.answered else None


@dataclass(frozen=True)
class Tally:
    items: dict[tuple[str, str], ItemCount]  # (kind, item id) -> counts
    uncertain: int
    empty: Counter  # kind -> contributions without text
    kinds: Counter  # kind -> contributions


def tally(pairs: Iterable[tuple[Evidence, Assessment]]) -> Tally:
    """Count met / not met per card item; 'not applicable' and 'uncertain' are left out."""
    items: dict[tuple[str, str], ItemCount] = {}
    uncertain = 0
    empty: Counter = Counter()
    kinds: Counter = Counter()
    for evidence, assessment in pairs:
        kinds[evidence.kind] += 1
        empty[evidence.kind] += assessment.empty
        for result in assessment.results:
            count = items.setdefault((evidence.kind, result.item_id), ItemCount())
            if result.answer == MET:
                count.met += 1
            elif result.answer == NOT_MET:
                count.not_met += 1
                if count.example is None and not assessment.empty:
                    count.example = (evidence, result.note)
            elif result.answer == UNCERTAIN:
                uncertain += 1
    return Tally(items, uncertain, empty, kinds)


def contributions_of(match: MatchResult, evidence: Iterable[Evidence]) -> list[Evidence]:
    """A student's own contributions: GitHub kinds by GitHub account, the rest by Taiga."""
    return [
        e for e in evidence if e.author in (match.github if e.kind in GITHUB_KINDS else match.taiga)
    ]


def report_file_name(name: str) -> str:
    return normalize_name(name).replace(" ", "-") + ".md"


def question(item: CardItem) -> str:
    """The question without its note for the model, e.g. '(Test yoksa uygulanamaz.)'."""
    return re.sub(r"\s*\([^()]*uygulanamaz\.?\)\s*$", "", item.question)


def short_note(note: str) -> str:
    """The first sentence, at most MAX_NOTE characters: notes come from the model."""
    first = note.strip().split(". ")[0].rstrip(".")
    return first if len(first) <= MAX_NOTE else first[: MAX_NOTE - 1].rstrip() + "…"


def student_report(
    name: str,
    pairs: Sequence[tuple[Evidence, Assessment]],
    cards: Mapping[str, Card],
    periods: Sequence[Period],
    method: str,
    agreement: float,
    today: date,
) -> str:
    """The Markdown report of one student."""
    total = tally(pairs)
    lines = [
        f"# Katkı geri bildirimi: {name}",
        "",
        "Bu rapor yalnızca sana aittir. Katkıların, beklenti kartlarındaki sorulara göre "
        "bilgisayarımızda çalışan dil modelleriyle değerlendirildi. Bu bir not değil, "
        "gelişimin için bir geri bildirimdir. Hatalı bulduğun bir değerlendirme olursa "
        "bağlantısıyla birlikte öğretim üyesine bildir.",
        "",
        f"- **Tarih:** {today.isoformat()}",
        f"- **Yöntem:** {method} "
        f"(öğretim üyesinin değerlendirmeleriyle uyuşma: {_percent(agreement)})",
        f"- **Değerlendirilen katkı:** {sum(total.kinds.values())} "
        f"({_kind_counts(total.kinds, cards)})",
        "",
    ]
    if not pairs:
        lines += ["Bu dönemde değerlendirilecek bir katkın bulunamadı.", ""]
        return "\n".join(lines)

    lines += _gaps(total, cards)
    lines += _strengths(total, cards)
    lines += _progress(pairs, cards, periods)
    lines += _notes(total, cards)
    return "\n".join(lines).rstrip() + "\n"


def _percent(rate: float) -> str:
    """Turkish style: %84."""
    return f"%{round(rate * 100)}"


def _item(cards: Mapping[str, Card], kind: str, item_id: str) -> CardItem:
    return next(i for i in cards[kind].items if i.id == item_id)


def _kind_counts(kinds: Counter, cards: Mapping[str, Card]) -> str:
    return ", ".join(f"{cards[k].title} {n}" for k, n in kinds.items() if k in cards)


def _gaps(total: Tally, cards: Mapping[str, Card]) -> list[str]:
    gaps = sorted(
        (
            (count.rate, -count.answered, key)
            for key, count in total.items.items()
            if count.rate is not None and count.rate < GAP_BELOW
        ),
    )[:MAX_GAPS]
    lines = ["## Geliştirebileceğin noktalar", ""]
    if not gaps:
        return lines + ["Belirgin bir eksik bulunmadı.", ""]
    for _, _, (kind, item_id) in gaps:
        count = total.items[(kind, item_id)]
        item = _item(cards, kind, item_id)
        industry = " *(sektör uygulaması)*" if item.industry else ""
        lines += [
            f"### {cards[kind].title}: {question(item)}",
            "",
            f"- **Karşılanma:** {count.met}/{count.answered} katkı",
            f"- **Öneri:** {item.tip}{industry}",
        ]
        if count.example:
            evidence, note = count.example
            lines.append(f"- **Örnek:** [{evidence.title}]({evidence.url}): {short_note(note)}")
        lines.append("")
    return lines


def _strengths(total: Tally, cards: Mapping[str, Card]) -> list[str]:
    strong = [
        (kind, item_id, count)
        for (kind, item_id), count in total.items.items()
        if count.rate == 1 and count.met >= MIN_FOR_STRENGTH
    ]
    if not strong:
        return []
    lines = ["## Güçlü yönlerin", ""]
    for kind, item_id, count in strong:
        item = _item(cards, kind, item_id)
        lines.append(f"- {cards[kind].title}: {question(item)} ({count.met}/{count.answered})")
    return lines + [""]


def _progress(
    pairs: Sequence[tuple[Evidence, Assessment]],
    cards: Mapping[str, Card],
    periods: Sequence[Period],
) -> list[str]:
    """Rates of the same items in each role period (REQ-7.7)."""
    if len(periods) < 2:
        return []
    by_period = [
        tally((e, a) for e, a in pairs if period.contains(e.created)).items for period in periods
    ]
    seen = {k for counts in by_period for k, c in counts.items() if c.answered}
    keys = [
        (kind, i.id) for kind, card in cards.items() for i in card.items if (kind, i.id) in seen
    ]
    rows = []
    for key in keys:
        cells = [counts.get(key) for counts in by_period]
        if sum(1 for c in cells if c and c.answered) < 2:
            continue  # progress needs the item in at least two periods
        item = _item(cards, *key)
        values = [f"{c.met}/{c.answered}" if c and c.answered else "–" for c in cells]
        rows.append(f"| {cards[key[0]].title}: {question(item)} | " + " | ".join(values) + " |")
    if not rows:
        return []
    header = "| Madde | " + " | ".join(p.name for p in periods) + " |"
    rule = "|---|" + "---|" * len(periods)
    return ["## Rol dönemlerine göre ilerleme", "", header, rule, *rows, ""]


def _notes(total: Tally, cards: Mapping[str, Card]) -> list[str]:
    lines = []
    for kind, number in total.empty.items():
        if number:
            why = " (yorumsuz onay)" if kind == "code_review" else ""
            lines.append(
                f"- {number} {cards[kind].title.lower()} metin içermiyordu{why}; "
                "bunlar bütün maddelerde karşılanmadı sayıldı."
            )
    if total.uncertain:
        lines.append(f"- {total.uncertain} madde, modeller anlaşamadığı için hesaba katılmadı.")
    return ["## Notlar", "", *lines, ""] if lines else []


def write_reports(
    matches: Sequence[MatchResult],
    evidence: Sequence[Evidence],
    assessments: Mapping[str, Assessment],
    cards: Mapping[str, Card],
    periods: Sequence[Period],
    method: str,
    agreement: float,
    folder: str | Path = DEFAULT_REPORT_DIR,
    today: date | None = None,
) -> list[Path]:
    """One file per matched student, plus the instructor's summary."""
    today = today or date.today()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    summary = [
        "# Nitel değerlendirme özeti (yalnızca öğretim üyesi)",
        "",
        f"Tarih: {today.isoformat()} · Yöntem: {method} · Uyuşma: {_percent(agreement)}",
        "",
        "| Öğrenci | Katkı | Eksik madde | Belirsiz | Şüpheli |",
        "|---|---|---|---|---|",
    ]
    suspicious_lines = []
    for match in matches:
        if match.unmatched:
            continue
        own = [e for e in contributions_of(match, evidence) if e.item_id in assessments]
        pairs = [(e, assessments[e.item_id]) for e in own]
        path = folder / report_file_name(match.student.name)
        path.write_text(
            student_report(match.student.name, pairs, cards, periods, method, agreement, today),
            encoding="utf-8",
        )
        written.append(path)
        total = tally(pairs)
        gaps = sum(1 for c in total.items.values() if c.rate is not None and c.rate < GAP_BELOW)
        flagged = [e for e, a in pairs if a.suspicious]
        suspicious_lines += [f"- {match.student.name}: [{e.title}]({e.url})" for e in flagged]
        summary.append(
            f"| {match.student.name} | {len(pairs)} | {gaps} | {total.uncertain} | {len(flagged)} |"
        )
    if suspicious_lines:
        summary += ["", "## Şüpheli metinler (değerlendirene yönelik talimat içerebilir)", ""]
        summary += suspicious_lines
    (folder / SUMMARY_FILE).write_text("\n".join(summary) + "\n", encoding="utf-8")
    return written
