"""Tests for matching students to GitHub and Taiga accounts (REQ-2.2 to REQ-2.5)."""

from contribution_tool.matching import match_students, normalize_name, unlinked_accounts
from contribution_tool.students import Student


def match(student, github_users=(), github_emails=None, taiga_users=None):
    return match_students([student], github_users, github_emails or {}, taiga_users or {})[0]


# REQ-2.2 — GitHub account from the e-mail used in commits


def test_email_used_in_commits_matches_github_login():
    student = Student(name="Test Öğrenci Bir", emails=("bir@example.org",))
    result = match(student, github_emails={"bir@example.org": ["ogrencibir"]})
    assert result.github == {"ogrencibir"}
    assert "GitHub: commit e-mail" in result.methods


def test_commit_email_is_compared_case_insensitively():
    student = Student(name="Test Öğrenci Bir", emails=("bir@example.org",))
    result = match(student, github_emails={"Bir@Example.ORG": ["OgrenciBir"]})
    assert result.github == {"ogrencibir"}


def test_email_not_used_in_commits_matches_nothing():
    student = Student(name="Test Öğrenci Bir", emails=("bir@example.org",))
    result = match(student, github_emails={"baska@example.org": ["baska"]})
    assert result.github == set()


def test_github_username_in_student_list_matches_active_login():
    student = Student(name="Test Öğrenci Bir", usernames=("ogrencibir",))
    result = match(student, github_users=["OgrenciBir"])
    assert result.github == {"ogrencibir"}


# REQ-2.3 — Taiga account: username, then full name, then e-mail prefix


def test_taiga_matches_by_username():
    student = Student(name="Test Öğrenci Bir", usernames=("ogrencibir",))
    result = match(student, taiga_users={"ogrencibir": "Başka Ad"})
    assert result.taiga == {"ogrencibir"}
    assert "Taiga: username" in result.methods


def test_taiga_matches_by_full_name_ignoring_turkish_letters_and_case():
    student = Student(name="Test Öğrenci İki")
    result = match(student, taiga_users={"t.iki": "TEST OGRENCI IKI"})
    assert result.taiga == {"t.iki"}
    assert "Taiga: full name" in result.methods


def test_taiga_matches_by_email_prefix():
    student = Student(name="Test Öğrenci Beş", emails=("bes@example.org",))
    result = match(student, taiga_users={"bes": "Farklı Yazılmış Ad"})
    assert result.taiga == {"bes"}
    assert "Taiga: e-mail prefix" in result.methods


def test_taiga_username_wins_over_full_name():
    student = Student(name="Test Öğrenci Bir", usernames=("ogrencibir",))
    taiga = {"ogrencibir": "Test Öğrenci Bir", "ikinci.hesap": "Test Öğrenci Bir"}
    assert match(student, taiga_users=taiga).taiga == {"ogrencibir"}


# Error guessing — names written differently


def test_normalize_name_handles_turkish_capitals_and_spaces():
    assert normalize_name("  İLKAY   IŞIK ") == "ilkay isik"
    assert normalize_name("Çağrı Şükrü Öğüt") == "cagri sukru ogut"


# REQ-2.4 — Unmatched student is flagged, never silently zero
# Source: bug reported by a student in the first role period


def test_student_without_any_account_is_flagged_unmatched():
    student = Student(name="Test Öğrenci Üç", emails=("uc@example.org",))
    result = match(student, github_users=["baska"], taiga_users={"baska": "Başka Kişi"})
    assert result.unmatched


def test_student_with_only_github_account_is_not_unmatched():
    student = Student(name="Test Öğrenci Bir", usernames=("ogrencibir",))
    assert not match(student, github_users=["ogrencibir"]).unmatched


# Acceptance test finding — same username in two columns counts once


def test_same_username_in_two_columns_is_linked_once():
    student = Student(name="Test Öğrenci Bir", usernames=("ogrencibir", "ogrencibir"))
    result = match(student, github_users=["ogrencibir"], taiga_users={"ogrencibir": "X"})
    assert result.github == {"ogrencibir"}
    assert result.taiga == {"ogrencibir"}


# REQ-2.5 — Active accounts that belong to no student


def test_unlinked_active_accounts_are_listed():
    students = [Student(name="Test Öğrenci Bir", usernames=("ogrencibir",))]
    results = match_students(students, ["ogrencibir"], {}, {})
    assert unlinked_accounts(results, ["ogrencibir", "Bilinmeyen", "dependabot"]) == [
        "bilinmeyen",
        "dependabot",
    ]


def test_no_unlinked_accounts_when_all_belong_to_students():
    students = [Student(name="Test Öğrenci Bir", usernames=("ogrencibir",))]
    results = match_students(students, ["ogrencibir"], {}, {})
    assert unlinked_accounts(results, ["ogrencibir"]) == []
