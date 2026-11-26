"""Tests for comparing models with the instructor's labels (REQ-7.10).

The models are fakes; every test runs in its own temporary folder.
"""

import csv
import json

import pytest

from contribution_tool import review_cli
from contribution_tool.cards import Card, CardItem
from contribution_tool.evidence import Evidence
from contribution_tool.review.agreement import (
    Agreement,
    evidence_from_sheet,
    format_agreement,
    measure,
    save_results,
)
from contribution_tool.review.assess import MET, NOT_MET
from contribution_tool.review.cache import Cache, assess_cached
from contribution_tool.review.calibration import write_label_sheet

CARDS = {
    "code_review": Card(
        kind="code_review",
        title="Kod incelemesi",
        items=(
            CardItem("review.finding", "Somut bulgu var mı?", "kaynak", "öneri"),
            CardItem("review.prefix", "Tür belirtilmiş mi?", "kaynak", "öneri"),
        ),
        fingerprint="card123",
    )
}


def contribution(number, text="zorunlu: BR-3.3 ihlali"):
    return Evidence(
        kind="code_review",
        author="ogrenciiki",
        created=None,
        title=f"Review on PR #{number}",
        text=text,
        url=f"https://example.org/pull/{number}",
        item_id=f"github:review:{number}",
    )


def model_saying(finding, prefix):
    """A fake model that always gives the same two answers."""

    def ask(system, prompt, schema):
        return {
            "review.finding": {"answer": finding, "note": "bulgu notu"},
            "review.prefix": {"answer": prefix, "note": "önek notu"},
            "suspicious": False,
        }

    return ask


def broken_model(system, prompt, schema):
    return {"suspicious": False}  # no answers


@pytest.fixture(autouse=True)
def in_temporary_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # data/ is created here, not in the repository


LABELS = {
    ("github:review:1", "review.finding"): MET,
    ("github:review:1", "review.prefix"): NOT_MET,
    ("github:review:2", "review.finding"): MET,
}


def run(ask, labels=LABELS):
    evidence = [contribution(1), contribution(2)]
    cache = Cache("cache")

    def judge(item, card):
        return assess_cached(item, card, ask, "m", cache)

    return measure("m", evidence, labels, CARDS, judge)


# Counting agreement


def test_every_label_is_compared_and_unlabelled_items_are_not():
    result = run(model_saying(MET, MET))
    assert (result.agreed, result.compared) == (2, 3)
    assert result.rate == pytest.approx(2 / 3)
    assert result.by_item == {"review.finding": [2, 2], "review.prefix": [0, 1]}


def test_disagreements_are_kept_with_the_models_note():
    (d,) = run(model_saying(MET, MET)).disagreements
    assert (d.evidence_id, d.item, d.label, d.answer, d.note) == (
        "github:review:1",
        "review.prefix",
        NOT_MET,
        MET,
        "önek notu",
    )


def test_a_contribution_the_model_cannot_answer_counts_against_it():
    result = run(broken_model)
    assert (result.agreed, result.compared, result.failed) == (0, 3, 2)
    assert {d.answer for d in result.disagreements} == {"error"}


def test_contribution_without_labels_is_not_sent_to_the_model():
    asked = []

    def counting(system, prompt, schema):
        asked.append(prompt)
        return model_saying(MET, MET)(system, prompt, schema)

    run(counting, labels={("github:review:2", "review.finding"): MET})
    assert len(asked) == 1


@pytest.mark.parametrize(
    ("agreed", "compared", "passed"),
    [(8, 10, True), (7, 10, False), (0, 0, False)],
    ids=["at-threshold", "below", "nothing-compared"],
)
def test_threshold_is_inclusive(agreed, compared, passed):
    assert Agreement("m", compared=compared, agreed=agreed).passed(0.8) is passed


# Reading the sheet, showing and saving the results


def test_contributions_are_read_back_from_the_sheet(tmp_path):
    path = write_label_sheet([contribution(1), contribution(2)], CARDS, tmp_path / "l.csv")
    evidence = evidence_from_sheet(path)
    assert [e.item_id for e in evidence] == ["github:review:1", "github:review:2"]
    assert evidence[0].text == "zorunlu: BR-3.3 ihlali"


def test_table_shows_the_best_model_first_and_its_weakest_items():
    good = Agreement("iyi-model", compared=10, agreed=9, by_item={"review.prefix": [4, 5]})
    weak = Agreement("zayif-model", compared=10, agreed=5)
    table = format_agreement([weak, good], 0.8)
    assert table.index("iyi-model") < table.index("zayif-model")
    assert "90%" in table and "yes" in table and "no" in table
    assert "review.prefix 80%" in table


def test_results_and_disagreements_are_saved():
    result = run(model_saying(MET, MET))
    path = save_results([result], 0.8, "data/results.json", "data/disagreements.csv")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["models"]["m"] == {
        "agreed": 2,
        "compared": 3,
        "failed": 0,
        "uncertain": 0,
        "rate": 0.6667,
        "passed": False,
    }
    with open("data/disagreements.csv", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [r["item"] for r in rows] == ["review.prefix"]


# The command


def labelled_sheet():
    path = write_label_sheet([contribution(1)], CARDS, "data/calibration/labels.csv")
    with path.open(encoding="utf-8-sig", newline="") as file:
        table = list(csv.DictReader(file))
    table[0]["label"], table[1]["label"] = "e", "h"
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    return path


def test_calibrate_command_prints_and_saves_the_rates(monkeypatch, capsys):
    labelled_sheet()
    monkeypatch.setattr(review_cli, "load_cards", lambda: CARDS)
    monkeypatch.setattr(review_cli, "ollama", lambda model: model_saying(MET, NOT_MET))
    assert review_cli.main(["calibrate", "--model", "a", "--model", "b"]) == 0
    out = capsys.readouterr().out
    assert "a " in out and "b " in out and "100%" in out
    saved = json.loads(open("data/calibration/results.json", encoding="utf-8").read())
    assert set(saved["models"]) == {"a", "b"}


def test_calibrate_without_labels_stops_with_message(monkeypatch, capsys):
    write_label_sheet([contribution(1)], CARDS, "data/calibration/labels.csv")
    monkeypatch.setattr(review_cli, "load_cards", lambda: CARDS)
    assert review_cli.main(["calibrate"]) == 1
    assert "fill in the label column" in capsys.readouterr().err


@pytest.mark.parametrize("threshold", ["0", "80", "-0.1"])
def test_threshold_outside_zero_to_one_is_refused(threshold):
    with pytest.raises(SystemExit):
        review_cli.parse_args(["calibrate", "--threshold", threshold])
