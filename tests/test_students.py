"""Tests for loading the student list (REQ-2.1)."""

import pytest

from contribution_tool.students import Student, load_students


def write_csv(tmp_path, text, encoding="utf-8"):
    path = tmp_path / "students.csv"
    path.write_text(text, encoding=encoding)
    return path


# REQ-2.1 — Equivalence partitioning: e-mail, username, both, empty


def test_value_with_at_sign_is_email(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,eposta\nTest Öğrenci Bir,bir@example.org\n")
    assert load_students(path) == [Student(name="Test Öğrenci Bir", emails=("bir@example.org",))]


def test_value_without_at_sign_is_username(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,github\nTest Öğrenci Bir,ogrencibir\n")
    assert load_students(path) == [Student(name="Test Öğrenci Bir", usernames=("ogrencibir",))]


def test_several_identifier_columns_are_combined(tmp_path):
    path = write_csv(
        tmp_path, "ad_soyad,eposta,github\nTest Öğrenci Bir,bir@example.org,ogrencibir\n"
    )
    student = load_students(path)[0]
    assert student.emails == ("bir@example.org",)
    assert student.usernames == ("ogrencibir",)


def test_empty_identifier_cells_are_ignored(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,eposta,github\nTest Öğrenci Bir,,ogrencibir\n")
    student = load_students(path)[0]
    assert student.emails == ()
    assert student.usernames == ("ogrencibir",)


def test_identifiers_are_trimmed_and_lowercased(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,eposta\nTest Öğrenci Bir, Bir@Example.ORG \n")
    assert load_students(path)[0].emails == ("bir@example.org",)


# REQ-2.1 — Name is mandatory


def test_missing_name_stops_with_line_number(tmp_path):
    path = write_csv(
        tmp_path, "ad_soyad,eposta\nTest Öğrenci Bir,bir@example.org\n,iki@example.org\n"
    )
    with pytest.raises(ValueError, match="Line 3"):
        load_students(path)


def test_missing_name_column_stops_with_error(tmp_path):
    path = write_csv(tmp_path, "isim,eposta\nTest Öğrenci Bir,bir@example.org\n")
    with pytest.raises(ValueError, match="ad_soyad"):
        load_students(path)


def test_blank_rows_are_skipped(tmp_path):
    path = write_csv(
        tmp_path,
        "ad_soyad,eposta\nTest Öğrenci Bir,bir@example.org\n,\nTest Öğrenci İki,iki@example.org\n",
    )
    assert len(load_students(path)) == 2


# REQ-2.1 — Error guessing: files saved by Excel


def test_utf8_bom_from_excel_is_handled(tmp_path):
    path = write_csv(
        tmp_path, "ad_soyad,eposta\nTest Öğrenci Bir,bir@example.org\n", encoding="utf-8-sig"
    )
    assert load_students(path)[0].name == "Test Öğrenci Bir"


def test_column_names_are_case_insensitive(tmp_path):
    path = write_csv(tmp_path, "Ad_Soyad,EPosta\nTest Öğrenci Bir,bir@example.org\n")
    assert load_students(path)[0].emails == ("bir@example.org",)


# REQ-2.1 — Role column selection


ROLES_CSV = "ad_soyad,rol_d1,rol_d2,eposta\nTest Öğrenci Bir,PO,Back,bir@example.org\n"


def test_first_role_column_is_used_by_default(tmp_path):
    assert load_students(write_csv(tmp_path, ROLES_CSV))[0].role == "PO"


def test_selected_role_column_is_used(tmp_path):
    path = write_csv(tmp_path, ROLES_CSV)
    assert load_students(path, role_column="rol_d2")[0].role == "Back"


def test_unknown_role_column_stops_with_error(tmp_path):
    path = write_csv(tmp_path, ROLES_CSV)
    with pytest.raises(ValueError, match="rol_d9"):
        load_students(path, role_column="rol_d9")


def test_role_is_empty_without_role_column(tmp_path):
    path = write_csv(tmp_path, "ad_soyad,eposta\nTest Öğrenci Bir,bir@example.org\n")
    assert load_students(path)[0].role == ""
