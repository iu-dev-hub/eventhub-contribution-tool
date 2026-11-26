"""Tests for the majority vote of several models (REQ-7.11).

The models are fakes; no test needs Ollama.
"""

import csv

import pytest

from contribution_tool import review_cli
from contribution_tool.cards import Card, CardItem
from contribution_tool.evidence import Evidence
from contribution_tool.github import GitHubData
from contribution_tool.review.assess import (
    MET,
    NOT_APPLICABLE,
    NOT_MET,
    Assessment,
    ItemResult,
    ModelResponseError,
)
from contribution_tool.review.calibration import write_label_sheet
from contribution_tool.review.vote import UNCERTAIN, majority, run_models, vote
from contribution_tool.taiga import TaigaData

CARD = Card(
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


def contribution(number=1):
    return Evidence(
        kind="code_review",
        author="ogrenciiki",
        created=None,
        title=f"Review on PR #{number}",
        text="zorunlu: BR-3.3 ihlali",
        url=f"https://example.org/pull/{number}",
        item_id=f"github:review:{number}",
    )


def answer(model, finding, question, suspicious=False):
    return Assessment(
        evidence_id="github:review:1",
        kind="code_review",
        author="ogrenciiki",
        results=(
            ItemResult("review.finding", finding, f"{model} bulgu notu"),
            ItemResult("review.question", question, f"{model} soru notu"),
        ),
        suspicious=suspicious,
        empty=False,
        content_hash="abc",
        card_fingerprint="card123",
        model=model,
    )


def answers_of(assessment):
    return [(r.item_id, r.answer) for r in assessment.results]


# The vote


def test_majority_answer_wins_with_its_note():
    result = vote(
        [answer("a", MET, MET), answer("b", MET, NOT_MET), answer("c", NOT_MET, NOT_MET)], "v"
    )
    assert answers_of(result) == [("review.finding", MET), ("review.question", NOT_MET)]
    assert result.results[0].note == "a bulgu notu"
    assert result.model == "v"


def test_three_different_answers_are_uncertain():
    result = vote(
        [answer("a", MET, MET), answer("b", MET, NOT_MET), answer("c", MET, NOT_APPLICABLE)],
        "v",
    )
    assert answers_of(result) == [("review.finding", MET), ("review.question", UNCERTAIN)]
    assert "anlaşamadı" in result.results[1].note


def test_any_model_can_flag_a_suspicious_text():
    result = vote([answer("a", MET, MET), answer("b", MET, MET, suspicious=True)], "v")
    assert result.suspicious


# Judges: failed models are left out


def judge_saying(*values, calls=None, name="m"):
    def judge(evidence, card):
        if calls is not None:
            calls.append((name, evidence.item_id))
        if values == ("fail",):
            raise ModelResponseError("not JSON")
        return answer(name, *values)

    return judge


def test_two_agreeing_models_decide_when_one_fails():
    judge = majority([judge_saying(MET, MET), judge_saying(MET, MET), judge_saying("fail")], "v")
    assert answers_of(judge(contribution(), CARD)) == [
        ("review.finding", MET),
        ("review.question", MET),
    ]


def test_one_against_one_is_uncertain_when_one_fails():
    judge = majority(
        [judge_saying(MET, MET), judge_saying(NOT_MET, MET), judge_saying("fail")], "v"
    )
    assert answers_of(judge(contribution(), CARD))[0] == ("review.finding", UNCERTAIN)


def test_no_usable_answer_at_all_is_an_error():
    judge = majority([judge_saying("fail"), judge_saying("fail")], "v")
    with pytest.raises(ModelResponseError, match="No model"):
        judge(contribution(), CARD)


# Running the models: one model at a time over every contribution


def test_each_model_runs_over_every_contribution_before_the_next_model():
    calls = []
    judges = {
        "a": judge_saying(MET, MET, calls=calls, name="a"),
        "b": judge_saying(MET, MET, calls=calls, name="b"),
    }
    run_models([contribution(1), contribution(2)], {"code_review": CARD}, judges)
    assert calls == [
        ("a", "github:review:1"),
        ("a", "github:review:2"),
        ("b", "github:review:1"),
        ("b", "github:review:2"),
    ]


def test_failures_are_counted_and_do_not_stop_the_run():
    judges = {"a": judge_saying("fail"), "b": judge_saying(MET, MET)}
    seen = []
    failed = run_models(
        [contribution(1), contribution(2)], {"code_review": CARD}, judges, seen.append
    )
    assert failed == {"a": 2, "b": 0}
    assert seen[-1] == "b: 2/2"


# The commands


@pytest.fixture
def fake_ollama(monkeypatch, tmp_path):
    """Every model gives the same answers; remembers which model was asked."""
    monkeypatch.chdir(tmp_path)  # data/cache is created here
    asked = []

    def ollama(model):
        def ask(system, prompt, schema):
            asked.append(model)
            return {
                "review.finding": {"answer": MET, "note": "not"},
                "review.question": {"answer": NOT_APPLICABLE, "note": "not"},
                "suspicious": False,
            }

        return ask

    monkeypatch.setattr(review_cli, "ollama", ollama)
    monkeypatch.setattr(review_cli, "load_cards", lambda: {"code_review": CARD})
    return asked


def test_assess_command_runs_each_model_once_and_reuses_saved_answers(
    fake_ollama, monkeypatch, capsys
):
    github = GitHubData()
    github.evidence.extend([contribution(1), contribution(2)])
    monkeypatch.setattr(review_cli, "collect", lambda args: (github, TaigaData()))
    args = ["assess", "--model", "a", "--model", "b"]
    assert review_cli.main(args) == 0
    assert fake_ollama == ["a", "a", "b", "b"]
    assert "0 reused, 4 new" in capsys.readouterr().err

    assert review_cli.main(args) == 0
    assert fake_ollama == ["a", "a", "b", "b"]  # nothing asked again
    assert "4 reused, 0 new" in capsys.readouterr().err


def labelled_sheet():
    path = write_label_sheet([contribution(1)], {"code_review": CARD}, "labels.csv")
    with path.open(encoding="utf-8-sig", newline="") as file:
        table = list(csv.DictReader(file))
    table[0]["label"], table[1]["label"] = "e", "u"
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    return str(path)


def test_calibrate_vote_adds_the_vote_of_the_models_that_pass(fake_ollama, capsys):
    args = ["calibrate", "--labels", labelled_sheet(), "--vote"]
    assert review_cli.main(args + ["--model", "a", "--model", "b", "--model", "c"]) == 0
    assert "vote:a+b+c" in capsys.readouterr().out
    assert fake_ollama == ["a", "b", "c"]  # the vote reused the saved answers


def test_calibrate_vote_needs_three_models_that_pass(fake_ollama, capsys):
    args = ["calibrate", "--labels", labelled_sheet(), "--vote", "--model", "a", "--model", "b"]
    assert review_cli.main(args) == 0
    captured = capsys.readouterr()
    assert "vote:" not in captured.out
    assert "No vote: 2 model(s) passed" in captured.err
