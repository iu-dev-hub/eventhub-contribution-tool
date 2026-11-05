"""Matching students to GitHub and Taiga accounts (REQ-2.2 to REQ-2.5, REQ-2.7)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from contribution_tool.students import Student

_TURKISH_TO_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def normalize_name(name: str) -> str:
    """Lowercase a full name, replace Turkish letters and collapse spaces."""
    # Python lowercases "İ" to "i" plus a combining dot, so Turkish capitals are mapped first
    name = name.replace("İ", "i").replace("I", "ı").lower()
    return " ".join(name.translate(_TURKISH_TO_ASCII).split())


@dataclass(frozen=True)
class MatchResult:
    student: Student
    github: frozenset[str]
    taiga: frozenset[str]
    methods: tuple[str, ...]
    unused: tuple[str, ...] = ()  # values in the student list that matched no account

    @property
    def unmatched(self) -> bool:
        """True when the student is linked to no account at all (REQ-2.4)."""
        return not self.github and not self.taiga

    @property
    def missing(self) -> tuple[str, ...]:
        """Sources the student is not linked to; empty when linked to both (REQ-2.4)."""
        return tuple(
            name
            for name, accounts in (("GitHub", self.github), ("Taiga", self.taiga))
            if not accounts
        )


def match_students(
    students: Iterable[Student],
    github_users: Iterable[str],
    github_emails: Mapping[str, Iterable[str]],
    taiga_users: Mapping[str, str],
) -> list[MatchResult]:
    """Link each student to GitHub and Taiga accounts.

    github_users:  GitHub logins that have activity in the repository
    github_emails: commit e-mail address -> GitHub logins that used it
    taiga_users:   Taiga username -> full name
    """
    gh_users = {login.lower() for login in github_users}
    gh_emails = {
        email.strip().lower(): {login.lower() for login in logins}
        for email, logins in github_emails.items()
    }
    tg_users = {username.lower(): full_name for username, full_name in taiga_users.items()}
    return [_match_one(student, gh_users, gh_emails, tg_users) for student in students]


def _match_one(
    student: Student,
    gh_users: set[str],
    gh_emails: dict[str, set[str]],
    tg_users: dict[str, str],
) -> MatchResult:
    methods = []

    # REQ-2.2: GitHub by username, and by the e-mail used in commits
    github = set(student.usernames) & gh_users
    if github:
        methods.append("GitHub: username")
    by_email = set().union(*(gh_emails.get(email, set()) for email in student.emails))
    if by_email:
        github |= by_email
        methods.append("GitHub: commit e-mail")

    # REQ-2.3: Taiga by username, then full name, then e-mail prefix (first hit wins)
    taiga = set(student.usernames) & tg_users.keys()
    if taiga:
        methods.append("Taiga: username")
    else:
        target = normalize_name(student.name)
        taiga = {user for user, full in tg_users.items() if normalize_name(full) == target}
        if taiga:
            methods.append("Taiga: full name")
        else:
            taiga = {email.split("@")[0] for email in student.emails} & tg_users.keys()
            if taiga:
                methods.append("Taiga: e-mail prefix")

    # REQ-2.7: values in the student list that point to no active account
    unused = [name for name in student.usernames if name not in gh_users | tg_users.keys()]
    unused += [
        email
        for email in student.emails
        if email not in gh_emails and email.split("@")[0] not in tg_users
    ]

    return MatchResult(
        student, frozenset(github), frozenset(taiga), tuple(methods), tuple(dict.fromkeys(unused))
    )


def unlinked_accounts(results: Iterable[MatchResult], active_accounts: Iterable[str]) -> list[str]:
    """Accounts with activity that belong to no student (REQ-2.5)."""
    linked = set().union(*(result.github | result.taiga for result in results))
    return sorted({account.lower() for account in active_accounts} - linked)
