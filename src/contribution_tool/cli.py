"""Command line interface (REQ-5.3)."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from contribution_tool.adjustments import load_adjustments
from contribution_tool.github import collect_github
from contribution_tool.github_api import (
    fetch_discussions,
    fetch_pull_requests,
    get_token,
    graphql_request,
)
from contribution_tool.report import Report, build_report
from contribution_tool.scoring import DEFAULT_TARGET_FACTOR
from contribution_tool.students import load_students
from contribution_tool.taiga import TaigaData, collect_taiga, load_csv, merge_taiga
from contribution_tool.taiga_api import (
    fetch_histories,
    get_credentials,
    ids_from_rows,
    login,
    taiga_request,
)
from contribution_tool.taiga_history import collect_history

DEFAULT_REPO = "iu-dev-hub/eventhub"
TAIGA_FILES = ("userstories.csv", "tasks.csv", "issues.csv")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="contribution-tool",
        description="Grade student contributions to EventHub from GitHub and Taiga.",
    )
    parser.add_argument("--students", required=True, type=Path, help="student list CSV")
    parser.add_argument("--taiga", type=Path, help=f"folder with {', '.join(TAIGA_FILES)}")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"default: {DEFAULT_REPO}")
    parser.add_argument("--start", type=date.fromisoformat, help="first day, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, help="last day, YYYY-MM-DD")
    parser.add_argument("--role", help="role column in the student list, e.g. rol_d1")
    parser.add_argument(
        "--factor", type=float, default=DEFAULT_TARGET_FACTOR, help="role target factor"
    )
    parser.add_argument("--adjustments", type=Path, help="instructor adjustments CSV")
    parser.add_argument(
        "--no-taiga-history",
        action="store_true",
        help="use only the Taiga CSV exports, without logging in to Taiga",
    )
    args = parser.parse_args(argv)
    if args.start and args.end and args.start > args.end:
        parser.error("--start must not be after --end")
    return args


def run(args: argparse.Namespace) -> Report:
    """Read all inputs, download GitHub data and build the report."""
    students = load_students(args.students, role_column=args.role)
    adjustments = load_adjustments(args.adjustments) if args.adjustments else []

    taiga = TaigaData()
    if args.taiga:
        stories, tasks, issues = _load_taiga_exports(args.taiga)
        taiga = collect_taiga(stories, tasks, issues, args.start, args.end)
        if not args.no_taiga_history:
            history = _taiga_history(stories, tasks, issues, args.start, args.end)
            taiga = merge_taiga(taiga, history)

    send = graphql_request(get_token())
    pull_requests = fetch_pull_requests(args.repo, send)
    discussions = fetch_discussions(args.repo, send)
    github = collect_github(pull_requests, discussions, args.start, args.end)

    return build_report(students, github, taiga, args.factor, adjustments)


def _load_taiga_exports(folder: Path) -> list[list[dict[str, str]]]:
    paths = [folder / name for name in TAIGA_FILES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Taiga export not found: {', '.join(missing)}")
    return [load_csv(path) for path in paths]


def _taiga_history(
    stories: list[dict[str, str]],
    tasks: list[dict[str, str]],
    issues: list[dict[str, str]],
    start: date | None,
    end: date | None,
) -> TaigaData:
    """Log in to Taiga and count work from the change history (REQ-1.7 to REQ-1.9)."""
    send = taiga_request(login(*get_credentials()))
    total = len(stories) + len(tasks) + len(issues)
    print(f"Downloading Taiga history for {total} items...", file=sys.stderr)
    story_histories = fetch_histories("userstory", ids_from_rows(stories), send)
    other_histories = fetch_histories("task", ids_from_rows(tasks), send)
    other_histories += fetch_histories("issue", ids_from_rows(issues), send)
    return collect_history(story_histories, other_histories, start, end)


def format_report(report: Report) -> str:
    """Plain text summary for the terminal."""
    width = max([len("Student")] + [len(r.name) for r in report.students])
    lines = [
        f"{'Student':<{width}}  {'Role':<13}  {'Grade':>9}  {'Adj':>4}  {'Final':>5}"
        f"  {'Score':>6}  Accounts"
    ]
    for r in report.students:
        grade = "UNMATCHED" if r.unmatched else str(r.grade)
        adjustment = f"{r.adjustment:+d}" if r.adjustment else ""
        final = "-" if r.final is None else str(r.final)
        accounts = ", ".join(r.accounts) or "-"
        lines.append(
            f"{r.name:<{width}}  {r.role:<13}  {grade:>9}  {adjustment:>4}  {final:>5}"
            f"  {r.score:>6.1f}  {accounts}"
        )

    adjusted = [r for r in report.students if r.reasons]
    if adjusted:
        lines += ["", "Adjustments:"]
        lines += [f"  - {r.name} {reason}" for r in adjusted for reason in r.reasons]
    if report.targets:
        lines += ["", "Role targets:"]
        lines += [f"  {role}: {target:.1f}" for role, target in sorted(report.targets.items())]
    if report.warnings:
        lines += ["", "Warnings:"]
        lines += [f"  - {warning}" for warning in report.warnings]
    if report.unlinked:
        lines += ["", "Active accounts not linked to any student:"]
        lines += [f"  - {account}" for account in report.unlinked]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run(args)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
