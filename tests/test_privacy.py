"""Tests for privacy and security rules (REQ-6.1 to REQ-6.3)."""

import os
import re
import subprocess
from pathlib import Path

import pytest

from contribution_tool.github_api import default_token_file, get_token

SOURCE = Path(__file__).parent.parent / "src"
ENV = "CONTRIBUTION_TOOL_TOKEN"
posix_only = pytest.mark.skipif(os.name == "nt", reason="file permissions are POSIX only")


@pytest.fixture
def no_file(tmp_path):
    """A token file path that does not exist, so a real file on this computer is not used."""
    return tmp_path / "missing" / "token"


def write_token(tmp_path, text, mode=0o600):
    path = tmp_path / "token"
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


# REQ-6.2 — The token comes from the environment or from a file outside the repository


def test_token_is_read_from_environment(no_file):
    assert get_token({ENV: "test-token"}, no_file) == "test-token"


@pytest.mark.parametrize("environ", [{}, {ENV: ""}, {ENV: "   "}])
def test_missing_token_stops_with_instructions(environ, no_file):
    with pytest.raises(RuntimeError, match="chmod 600"):
        get_token(environ, no_file)


def test_github_token_variable_is_not_used(no_file):
    # Regression: GITHUB_TOKEN is also used by git and gh; reading it broke git push
    with pytest.raises(RuntimeError):
        get_token({"GITHUB_TOKEN": "test-token"}, no_file)


def test_token_is_read_from_file(tmp_path):
    assert get_token({}, write_token(tmp_path, "file-token\n")) == "file-token"


def test_environment_wins_over_file(tmp_path):
    assert get_token({ENV: "env-token"}, write_token(tmp_path, "file-token")) == "env-token"


def test_empty_file_stops_with_error(tmp_path):
    with pytest.raises(RuntimeError, match="is empty"):
        get_token({}, write_token(tmp_path, "  \n"))


@posix_only
def test_file_readable_by_others_gives_a_warning(tmp_path):
    warnings = []
    get_token({}, write_token(tmp_path, "file-token", mode=0o644), warn=warnings.append)
    assert len(warnings) == 1
    assert "chmod 600" in warnings[0]


@posix_only
def test_private_file_gives_no_warning(tmp_path):
    warnings = []
    get_token({}, write_token(tmp_path, "file-token", mode=0o600), warn=warnings.append)
    assert warnings == []


def test_default_file_is_in_the_config_folder():
    path = default_token_file({"XDG_CONFIG_HOME": "/home/x/.config"}, os_name="posix")
    assert path == Path("/home/x/.config/contribution-tool/token")


def test_default_file_on_windows_is_in_appdata():
    path = default_token_file({"APPDATA": "C:/Users/x/AppData/Roaming"}, os_name="nt")
    assert path == Path("C:/Users/x/AppData/Roaming/contribution-tool/token")


def test_no_token_is_written_in_source_code():
    # GitHub tokens start with ghp_ (classic) or github_pat_ (fine-grained)
    pattern = re.compile(r"(ghp_|github_pat_)[A-Za-z0-9_]{10,}")
    leaks = [str(path) for path in SOURCE.rglob("*.py") if pattern.search(path.read_text())]
    assert leaks == []


# REQ-6.1 — Student data, output files and secrets cannot be committed

ROOT = Path(__file__).parent.parent
in_git = pytest.mark.skipif(
    subprocess.run(["git", "-C", str(ROOT), "rev-parse"], capture_output=True).returncode != 0,
    reason="not a git checkout",
)


@in_git
@pytest.mark.parametrize(
    "path",
    [
        "data/ogrenciler.csv",
        "data/taiga/issues.csv",
        "data/duzeltmeler_d1.csv",
        "data/rapor_d1.xlsx",
        "ogrenciler.csv",
        "rapor.xlsx",
        ".env",
    ],
)
def test_private_files_are_ignored_by_git(path):
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", path])
    assert ignored.returncode == 0, f"{path} is not ignored by .gitignore"


@in_git
def test_no_private_file_is_committed():
    files = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split()
    private = [f for f in files if f.startswith("data/") or f.endswith((".xlsx", ".xls", ".env"))]
    assert private == []


# REQ-6.3 — Test data is made up: e-mail addresses use reserved example domains


def test_test_data_uses_only_example_email_domains():
    email = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
    domains = {
        match.lower()
        for path in Path(__file__).parent.rglob("*.py")
        for match in email.findall(path.read_text(encoding="utf-8"))
    }
    assert domains <= {"example.org", "example.com"}, f"real-looking domains: {domains}"
