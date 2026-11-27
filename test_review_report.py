"""Tests for the per-student reports (REQ-7.6 to REQ-7.10).

Made-up students and contributions only; every file goes to a temporary folder.
"""

import json
from datetime import date

import pytest

from contribution_tool import review_cli
from contribution_tool.cards import Card, CardItem
from contribution_tool.evidence import Evidence
from contribution_tool.github import GitHubData
from contribution_tool.matching import MatchResult
from contribution_tool.review.agreement import calibrated
from contribution_tool.review.assess import (
    MET,
    NOT_APPLICABLE,
    NOT_MET,
    Assessment,
    ItemResult,
)
from contribution_tool.review.report import (
    SUMMARY_FILE,
    Period,
    contributions_of,
    parse_period,
    report_file_name,
    short_note,
    student_report,
    tally,
    write_reports,
)
from contribution_tool.review.vote import UNCERTAIN
from contribution_tool.students import Student
from contribution_tool.taiga import TaigaData

CARDS = {
    "pull_request": Card(
        kind="pull_request",
        title="Pull request",
        items=(
            CardItem("pr.tg", "TG numarası var mı?", "kaynak", "Başlığa TG-42 yazın."),
            CardItem("pr.why", "Neden yapıldığı yazılmış mı?", "kaynak", "Nedenini yazın.", True),
            CardItem(
                "pr.tests",
                "Test sonucu var mı? (Test yoksa uygulanamaz.)",
                "kaynak",
                "Test çıktısını ekleyin.",
                not_applicable=True,
            ),
        ),
        fingerprint="card123",
    ),
    "user_story": Card(
        kind="user_story",
        title="Kullanıcı hikâyesi",
        items=(CardItem("story.criteria", "Kabul kriteri var mı?", "kaynak", "Ekleyin."),),
        fingerprint="card456",
    ),
}

TODAY = date(2026, 11, 27)


def pr(number, author="ogrencibir", created=date(2026, 10, 5), text="TG-42 ekledim"):
    return Evidence(
        kind="pull_request",
        author=author,
        created=created,
        title=f"PR #{number}",
        text=text,
        url=f"https://example.org/pull/{number}",
        item_id=f"github:pr:{number}",
    )


def story(number, author="ogrencibir"):
    return Evidence(
        kind="user_story",
        author=author,
        created=date(2026, 10, 5),
        title=f"Hikâye #{number}",
        text="Bir katılımcı olarak...",
        url=f"https://example.org/us/{number}",
        item_id=f"taiga:us:{number}",
    )


def assessed(evidence, *answers, suspicious=False, empty=False):
    items = CARDS[evidence.kind].items
    return Assessment(
        evidence_id=evidence.item_id,
        kind=evidence.kind,
        author=evidence.author,
        results=tuple(
            ItemResult(item.id, answer, f"{item.id} notu. İkinci cümle.")
            for item, answer in zip(items, answers, strict=True)
        ),
        suspicious=suspicious,
        empty=empty,
        content_hash="abc",
        card_fingerprint=CARDS[evidence.kind].fingerprint,
        model="vote",
    )


def match(name="Test Öğrenci Bir", github=("ogrencibir",), taiga=("ogrencibir",)):
    return MatchResult(Student(name), frozenset(github), frozenset(taiga), ("test",))


def report(pairs, periods=()):
    return student_report("Test Öğrenci Bir", pairs, CARDS, periods, "3 modelin oyu", 0.84, TODAY)


# Periods


def test_period_is_read_from_text():
    assert parse_period("D1=2026-09-29..2026-11-02") == Period(
        "D1", date(2026, 9, 29), date(2026, 11, 2)
    )


@pytest.mark.parametrize("text", ["D1", "D1=2026-09-29", "D1=2026-11-02..2026-09-29"])
def test_wrong_period_stops_with_message(text):
    with pytest.raises(ValueError, match="Period"):
        parse_period(text)


# Counting (REQ-7.6)


def test_not_applicable_and_uncertain_are_left_out_of_the_rate():
    counts = tally(
        [
            (pr(1), assessed(pr(1), MET, NOT_MET, NOT_APPLICABLE)),
            (pr(2), assessed(pr(2), NOT_MET, UNCERTAIN, NOT_APPLICABLE)),
        ]
    )
    assert counts.items[("pull_request", "pr.tg")].rate == 0.5
    assert counts.items[("pull_request", "pr.why")].answered == 1
    assert counts.items[("pull_request", "pr.tests")].rate is None
    assert counts.uncertain == 1


def test_example_of_a_gap_is_a_contribution_with_text():
    empty, written = pr(1, text=""), pr(2)
    counts = tally(
        [
            (empty, assessed(empty, NOT_MET, NOT_MET, NOT_MET, empty=True)),
            (written, assessed(written, NOT_MET, MET, MET)),
        ]
    )
    assert counts.items[("pull_request", "pr.tg")].example[0] == written
    assert counts.empty["pull_request"] == 1


def test_github_work_is_found_by_github_account_and_taiga_work_by_taiga_account():
    evidence = [pr(1, author="ayni"), story(1, author="ayni"), pr(2, author="baska")]
    student = match(github=("ayni",), taiga=())
    assert [e.item_id for e in contributions_of(student, evidence)] == ["github:pr:1"]


# The report (REQ-7.6 to REQ-7.8)


def test_gaps_show_the_cards_tip_and_an_example():
    text = report([(pr(1), assessed(pr(1), NOT_MET, NOT_MET, NOT_APPLICABLE))])
    assert "### Pull request: TG numarası var mı?" in text
    assert "**Karşılanma:** 0/1 katkı" in text
    assert "**Öneri:** Başlığa TG-42 yazın." in text
    assert "Nedenini yazın. *(sektör uygulaması)*" in text
    assert "[PR #1](https://example.org/pull/1): pr.tg notu" in text
    assert "İkinci cümle" not in text  # only the first sentence of the model's note
    assert "Test çıktısını" not in text  # not applicable is not a gap
    assert "REQ-" not in text  # students read this, not the requirements


def test_strengths_need_at_least_two_contributions():
    one = report([(pr(1), assessed(pr(1), MET, MET, MET))])
    two = report([(p, assessed(p, MET, NOT_MET, MET)) for p in (pr(1), pr(2))])
    assert "Güçlü yönlerin" not in one
    assert "- Pull request: TG numarası var mı? (2/2)" in two


def test_progress_compares_the_same_items_in_each_period():
    early, late = pr(1, created=date(2026, 10, 5)), pr(2, created=date(2026, 11, 10))
    periods = [
        Period("D1", date(2026, 9, 29), date(2026, 11, 2)),
        Period("D2", date(2026, 11, 3), date(2026, 11, 30)),
    ]
    text = report(
        [
            (early, assessed(early, NOT_MET, NOT_MET, MET)),
            (late, assessed(late, MET, NOT_MET, NOT_APPLICABLE)),
        ],
        periods,
    )
    assert "| Madde | D1 | D2 |" in text
    assert "| Pull request: TG numarası var mı? | 0/1 | 1/1 |" in text
    assert "Test sonucu" not in text.split("| Madde |")[1]  # only in one period


def test_empty_texts_and_uncertain_items_are_explained():
    empty = pr(1, text="")
    text = report(
        [
            (empty, assessed(empty, NOT_MET, NOT_MET, NOT_MET, empty=True)),
            (pr(2), assessed(pr(2), UNCERTAIN, MET, MET)),
        ]
    )
    assert "1 pull request metin içermiyordu" in text
    assert "1 madde, modeller anlaşamadığı için" in text


def test_report_without_contributions_says_so():
    assert "değerlendirilecek bir katkın bulunamadı" in report([])


def test_agreement_is_written_the_turkish_way():
    assert "uyuşma: %84" in report([])


def test_short_note_keeps_the_first_sentence_and_at_most_200_characters():
    assert short_note("Bulgu var. Ama gerekçe yok.") == "Bulgu var"
    assert len(short_note("a" * 500)) == 200


def test_questions_are_shown_without_the_note_for_the_model():
    text = report([(pr(1), assessed(pr(1), MET, MET, NOT_MET))])
    assert "### Pull request: Test sonucu var mı?\n" in text


def test_file_name_has_no_turkish_letters_or_spaces():
    assert report_file_name("Test Öğrenci Bir") == "test-ogrenci-bir.md"


# Writing the files (REQ-7.9)


def test_each_student_gets_only_their_own_report(tmp_path):
    evidence = [pr(1, author="ogrencibir"), pr(2, author="ogrenciiki")]
    assessments = {
        "github:pr:1": assessed(evidence[0], MET, MET, MET),
        "github:pr:2": assessed(evidence[1], NOT_MET, MET, MET, suspicious=True),
    }
    matches = [
        match("Test Öğrenci Bir", ("ogrencibir",), ()),
        match("Test Öğrenci İki", ("ogrenciiki",), ()),
        match("Test Öğrenci Üç", (), ()),  # matched to no account: no report
    ]
    written = write_reports(matches, evidence, assessments, CARDS, [], "oy", 0.84, tmp_path, TODAY)
    assert [p.name for p in written] == ["test-ogrenci-bir.md", "test-ogrenci-iki.md"]
    first = written[0].read_text(encoding="utf-8")
    assert "PR #2" not in first and "İki" not in first

    summary = (tmp_path / SUMMARY_FILE).read_text(encoding="utf-8")
    assert "| Test Öğrenci İki | 1 | 1 | 0 | 1 |" in summary
    assert "- Test Öğrenci İki: [PR #2](https://example.org/pull/2)" in summary


# Calibration must have passed (REQ-7.10)


def results(tmp_path, models):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"threshold": 0.8, "models": models}), encoding="utf-8")
    return path


def test_vote_is_found_whatever_the_order_of_its_models(tmp_path):
    path = results(tmp_path, {"vote:b+a+c": {"rate": 0.86, "passed": True}})
    assert calibrated(["a", "b", "c"], path) == ("vote:b+a+c", 0.86)


@pytest.mark.parametrize(
    ("models", "saved"),
    [
        (["a"], {"a": {"rate": 0.7, "passed": False}}),
        (["a", "b", "c"], {"a": {"rate": 0.9, "passed": True}}),  # only single models
        (["a", "b", "c"], {"vote:a+b": {"rate": 0.9, "passed": True}}),  # other voters
    ],
)
def test_method_that_did_not_pass_makes_no_reports(tmp_path, models, saved):
    with pytest.raises(ValueError, match="REQ-7.10"):
        calibrated(models, results(tmp_path, saved))


def test_missing_calibration_says_what_to_run(tmp_path):
    with pytest.raises(ValueError, match="calibrate --vote"):
        calibrated(["a"], tmp_path / "missing.json")


# The command


def test_report_command_stops_before_downloading_if_not_calibrated(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    def must_not_download(args):
        raise AssertionError("no download before the calibration check")

    monkeypatch.setattr(review_cli, "collect", must_not_download)
    assert review_cli.main(["report", "--students", "ogrenciler.csv"]) == 1
    assert "calibrate --vote" in capsys.readouterr().err


def test_report_command_writes_the_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "calibration").mkdir(parents=True)
    results(tmp_path / "data" / "calibration", {"m": {"rate": 0.85, "passed": True}})
    (tmp_path / "ogrenciler.csv").write_text(
        "ad_soyad,github\nTest Öğrenci Bir,ogrencibir\n", encoding="utf-8"
    )
    github = GitHubData()
    github.counts["ogrencibir"]["pull_requests"] = 1
    github.evidence.append(pr(1))

    def ollama(model):
        def ask(system, prompt, schema):
            return {
                "pr.tg": {"answer": MET, "note": "var"},
                "pr.why": {"answer": NOT_MET, "note": "neden yok"},
                "pr.tests": {"answer": NOT_APPLICABLE, "note": "test yok"},
                "suspicious": False,
            }

        return ask

    monkeypatch.setattr(review_cli, "collect", lambda args: (github, TaigaData()))
    monkeypatch.setattr(review_cli, "ollama", ollama)
    monkeypatch.setattr(review_cli, "load_cards", lambda: CARDS)
    assert review_cli.main(["report", "--students", "ogrenciler.csv", "--model", "m"]) == 0
    text = (tmp_path / "data" / "reports" / "test-ogrenci-bir.md").read_text(encoding="utf-8")
    assert "Neden yapıldığı yazılmış mı?" in text
    assert "Saved 1 student reports" in capsys.readouterr().err


def test_two_models_cannot_vote(capsys):
    args = ["report", "--students", "x.csv", "--model", "a", "--model", "b"]
    assert review_cli.main(args) == 1
    assert "not two" in capsys.readouterr().err
