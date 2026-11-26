"""Tests for the instructor's label file (REQ-7.10).

Made-up contributions only; every file goes to a temporary folder.
"""

import csv

import pytest

from contribution_tool import review_cli
from contribution_tool.cards import Card, CardItem
from contribution_tool.evidence import Evidence
from contribution_tool.github import GitHubData
from contribution_tool.review.assess import MAX_CHARS, MET, NOT_APPLICABLE, NOT_MET
from contribution_tool.review.calibration import (
    LabelError,
    choose_sample,
    load_labels,
    write_label_sheet,
)
from contribution_tool.taiga import TaigaData

CARDS = {
    "code_review": Card(
        kind="code_review",
        title="Kod incelemesi",
        items=(
            CardItem("review.finding", "Somut bulgu var mı?", "kaynak", "öneri"),
            CardItem(
                "review.question",
                "Soruysa açık mı? (Soru değilse uygulanamaz.)",
                "kaynak",
                "öneri",
                not_applicable=True,
            ),
        ),
        fingerprint="card123",
    )
}


def contribution(number, kind="code_review", text="zorunlu: BR-3.3 ihlali"):
    return Evidence(
        kind=kind,
        author="ogrenciiki",
        created=None,
        title=f"Review on PR #{number}",
        text=text,
        url=f"https://example.org/pull/{number}",
        item_id=f"github:review:{number}",
    )


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_labels(path, labels):
    """Fill in the label column as the instructor would."""
    table = rows(path)
    for row, label in zip(table, labels, strict=True):
        row["label"] = label
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)


# Choosing the sample


def test_sample_takes_a_few_of_each_kind():
    evidence = [contribution(n) for n in range(20)]
    evidence += [contribution(n, kind="bug_report") for n in range(2)]
    sample = choose_sample(evidence, per_kind=5)
    kinds = [e.kind for e in sample]
    assert kinds.count("code_review") == 5
    assert kinds.count("bug_report") == 2  # fewer exist than asked for


def test_sample_is_the_same_every_time_whatever_the_order():
    evidence = [contribution(n) for n in range(20)]
    first = choose_sample(evidence)
    assert choose_sample(list(reversed(evidence))) == first


def test_empty_texts_are_not_chosen():
    evidence = [contribution(1, text="  "), contribution(2)]
    assert [e.item_id for e in choose_sample(evidence)] == ["github:review:2"]


# The label sheet


def test_sheet_has_one_row_per_item_and_the_text_once(tmp_path):
    path = write_label_sheet([contribution(1)], CARDS, tmp_path / "labels.csv")
    table = rows(path)
    assert [(r["item"], r["answers"]) for r in table] == [
        ("review.finding", "e / h"),
        ("review.question", "e / h / u"),
    ]
    assert table[0]["text"] == "zorunlu: BR-3.3 ihlali"
    assert table[1]["text"] == ""
    assert {r["label"] for r in table} == {""}


def test_sheet_shows_the_same_part_of_the_text_as_the_model(tmp_path):
    long = contribution(1, text="a" * (MAX_CHARS + 50))
    path = write_label_sheet([long], CARDS, tmp_path / "labels.csv")
    assert "metin kısaltıldı" in rows(path)[0]["text"]


def test_existing_sheet_is_never_overwritten(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text("evidence_id,label\nx,e\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="labels"):
        write_label_sheet([contribution(1)], CARDS, path)
    assert "x,e" in path.read_text(encoding="utf-8")


# Reading the labels back


def test_labels_are_read_in_short_or_long_form(tmp_path):
    path = write_label_sheet([contribution(1), contribution(2)], CARDS, tmp_path / "l.csv")
    write_labels(path, ["e", "U", "hayır", ""])
    assert load_labels(path, CARDS) == {
        ("github:review:1", "review.finding"): MET,
        ("github:review:1", "review.question"): NOT_APPLICABLE,
        ("github:review:2", "review.finding"): NOT_MET,
    }


@pytest.mark.parametrize(
    ("labels", "message"),
    [
        (["belki", ""], "Line 2: 'belki' is not a label"),
        (["u", ""], "Line 2: 'review.finding' cannot be 'uygulanamaz'"),
    ],
)
def test_wrong_label_stops_with_the_line_number(tmp_path, labels, message):
    path = write_label_sheet([contribution(1)], CARDS, tmp_path / "l.csv")
    write_labels(path, labels)
    with pytest.raises(LabelError, match=message):
        load_labels(path, CARDS)


# The command


def test_sheet_command_writes_the_file(tmp_path, monkeypatch, capsys):
    github = GitHubData()
    github.evidence.extend(contribution(n) for n in range(3))
    monkeypatch.setattr(review_cli, "collect", lambda args: (github, TaigaData()))
    monkeypatch.setattr(review_cli, "load_cards", lambda: CARDS)
    out = tmp_path / "labels.csv"
    assert review_cli.main(["sheet", "--out", str(out)]) == 0
    assert len(rows(out)) == 6
    assert "Saved 3 contributions" in capsys.readouterr().err


def test_sheet_command_refuses_to_overwrite(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(review_cli, "collect", lambda args: (GitHubData(), TaigaData()))
    out = tmp_path / "labels.csv"
    out.write_text("dolu\n", encoding="utf-8")
    assert review_cli.main(["sheet", "--out", str(out)]) == 1
    assert "already exists" in capsys.readouterr().err
