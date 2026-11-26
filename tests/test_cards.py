"""Tests for expectation cards (REQ-7.2)."""

import re

import pytest

from contribution_tool.cards import load_card, load_cards
from contribution_tool.evidence import KINDS

ITEM = """
[[items]]
id = "x.one"
question = "Soru?"
source = "kaynak"
tip = "öneri"
"""


def write_card(tmp_path, text, name="card.toml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# The real cards in the repository


def test_every_contribution_kind_has_a_card():
    assert set(load_cards()) == set(KINDS)


def test_every_item_id_starts_with_the_same_prefix_in_a_card():
    for card in load_cards().values():
        prefixes = {item.id.split(".")[0] for item in card.items}
        assert len(prefixes) == 1, card.kind


def test_review_card_answers_issue_68():
    ids = [item.id for item in load_cards()["code_review"].items]
    assert "review.finding" in ids


def test_industry_items_name_a_source_outside_eventhub():
    items = [item for card in load_cards().values() for item in card.items if item.industry]
    assert items
    for item in items:
        sources = [part.strip() for part in item.source.split(";")]
        assert any(not part.startswith("eventhub") for part in sources), item.id


def test_not_applicable_is_allowed_exactly_where_the_question_mentions_it():
    for card in load_cards().values():
        for item in card.items:
            assert item.not_applicable == ("uygulanamaz" in item.question), item.id


def test_questions_are_asked_positively():
    # Found in calibration: "...yazılmamış mı?" confused every model ("met" meant "absent")
    negative = re.compile(r"m[ae]m[ıi]ş m[ıi]\?|m[ae]z m[ıi]\?|m[ae]yor mu\?")
    for card in load_cards().values():
        for item in card.items:
            assert not negative.search(item.question), item.id


# Checking card files


def test_valid_card_is_loaded(tmp_path):
    card = load_card(write_card(tmp_path, 'kind = "bug_report"\ntitle = "Hata"\n' + ITEM))
    assert card.kind == "bug_report"
    assert [item.id for item in card.items] == ["x.one"]
    assert card.items[0].industry is False


def test_unknown_kind_stops_with_error(tmp_path):
    with pytest.raises(ValueError, match="commit"):
        load_card(write_card(tmp_path, 'kind = "commit"\ntitle = "x"\n' + ITEM))


def test_item_without_tip_stops_with_error(tmp_path):
    text = 'kind = "bug_report"\ntitle = "x"\n' + ITEM.replace('tip = "öneri"', 'tip = ""')
    with pytest.raises(ValueError, match="item 1 is missing tip"):
        load_card(write_card(tmp_path, text))


def test_duplicate_item_id_stops_with_error(tmp_path):
    with pytest.raises(ValueError, match="used twice"):
        load_card(write_card(tmp_path, 'kind = "bug_report"\ntitle = "x"\n' + ITEM + ITEM))


def test_card_without_items_stops_with_error(tmp_path):
    with pytest.raises(ValueError, match="at least one item"):
        load_card(write_card(tmp_path, 'kind = "bug_report"\ntitle = "x"\n'))


def test_missing_card_for_a_kind_stops_with_error(tmp_path):
    write_card(tmp_path, 'kind = "bug_report"\ntitle = "x"\n' + ITEM)
    with pytest.raises(ValueError, match="No card for"):
        load_cards(tmp_path)


def test_fingerprint_changes_when_the_card_changes(tmp_path):
    path = write_card(tmp_path, 'kind = "bug_report"\ntitle = "x"\n' + ITEM)
    before = load_card(path).fingerprint
    path.write_text(path.read_text(encoding="utf-8").replace("Soru?", "Yeni soru?"), "utf-8")
    assert load_card(path).fingerprint != before
