"""Command line for the qualitative review (REQ-7)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contribution_tool.cards import load_cards
from contribution_tool.cli import add_source_arguments, check_dates, collect
from contribution_tool.matching import match_students
from contribution_tool.review.agreement import (
    CANDIDATES,
    DEFAULT_DISAGREEMENTS,
    DEFAULT_RESULTS,
    DEFAULT_THRESHOLD,
    calibrated,
    evidence_from_sheet,
    format_agreement,
    measure,
    save_results,
)
from contribution_tool.review.assess import ModelResponseError
from contribution_tool.review.cache import Cache, assess_cached
from contribution_tool.review.calibration import (
    DEFAULT_SHEET,
    PER_KIND,
    choose_sample,
    load_labels,
    write_label_sheet,
)
from contribution_tool.review.llm import ollama
from contribution_tool.review.report import (
    DEFAULT_REPORT_DIR,
    SUMMARY_FILE,
    parse_period,
    write_reports,
)
from contribution_tool.review.vote import VOTERS, Judge, majority, run_models
from contribution_tool.students import load_students

MIN_VOTERS = 3  # with two models, every disagreement would be "uncertain"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="contribution-review",
        description="Review student contributions with a local model.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sheet = commands.add_parser(
        "sheet", help="write a sample of contributions for the instructor's labels"
    )
    add_source_arguments(sheet)
    sheet.add_argument("--out", type=Path, default=DEFAULT_SHEET, help=f"default: {DEFAULT_SHEET}")
    sheet.add_argument(
        "--per-kind",
        type=int,
        default=PER_KIND,
        help=f"contributions per kind (default {PER_KIND})",
    )

    calibrate = commands.add_parser(
        "calibrate", help="compare local models with the instructor's labels"
    )
    calibrate.add_argument(
        "--labels", type=Path, default=DEFAULT_SHEET, help=f"default: {DEFAULT_SHEET}"
    )
    calibrate.add_argument(
        "--model",
        action="append",
        help=f"model to test; repeat for several (default: {', '.join(CANDIDATES)})",
    )
    calibrate.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"lowest agreement rate a model needs (default {DEFAULT_THRESHOLD})",
    )
    calibrate.add_argument(
        "--vote",
        action="store_true",
        help=f"also measure the majority vote of the models that pass (at least {MIN_VOTERS})",
    )

    run = commands.add_parser(
        "assess", help="run the models over every contribution and save their answers"
    )
    add_source_arguments(run)
    run.add_argument(
        "--model",
        action="append",
        help=f"model to run; repeat for several (default: {', '.join(VOTERS)})",
    )

    report = commands.add_parser(
        "report", help="write one private Markdown report per student (REQ-7.6 to REQ-7.9)"
    )
    report.add_argument("--students", required=True, type=Path, help="student list CSV")
    report.add_argument("--role", help="role column in the student list, e.g. rol_d1")
    add_source_arguments(report)
    report.add_argument(
        "--model",
        action="append",
        help=f"model(s) whose answers are used; several = vote (default: {', '.join(VOTERS)})",
    )
    report.add_argument(
        "--period",
        action="append",
        type=parse_period,
        default=[],
        help="role period for the progress table, e.g. D1=2026-09-29..2026-11-02 (repeat)",
    )
    report.add_argument(
        "--out", type=Path, default=DEFAULT_REPORT_DIR, help=f"default: {DEFAULT_REPORT_DIR}"
    )

    args = parser.parse_args(argv)
    if args.command in ("sheet", "assess", "report"):
        check_dates(commands.choices[args.command], args)
    elif not 0 < args.threshold <= 1:
        calibrate.error("--threshold must be between 0 and 1, e.g. 0.8")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "sheet":
            _sheet(args)
        elif args.command == "assess":
            _assess(args)
        elif args.command == "report":
            _report(args)
        else:
            _calibrate(args)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


def _sheet(args: argparse.Namespace) -> None:
    github, taiga = collect(args)
    sample = choose_sample(github.evidence + taiga.evidence, args.per_kind)
    path = write_label_sheet(sample, load_cards(), args.out)
    print(f"Saved {len(sample)} contributions for labelling: {path}", file=sys.stderr)


def _calibrate(args: argparse.Namespace) -> None:
    """Ask each model about the labelled contributions; saved answers are reused."""
    cards = load_cards()
    labels = load_labels(args.labels, cards)
    if not labels:
        raise ValueError(f"No labels in {args.labels}: fill in the label column first")
    evidence = evidence_from_sheet(args.labels)
    cache = Cache()
    models = args.model or list(CANDIDATES)
    judges = {model: _judge(model, cache) for model in models}
    results = []
    for model in models:
        print(f"Asking {model} ({len(labels)} labels)...", file=sys.stderr)
        results.append(measure(model, evidence, labels, cards, judges[model]))
    if args.vote:
        voters = [r.model for r in results if r.passed(args.threshold)]
        if len(voters) >= MIN_VOTERS:
            name = "vote:" + "+".join(voters)
            print(f"Voting: {', '.join(voters)}", file=sys.stderr)
            judge = majority([judges[model] for model in voters], name)
            results.append(measure(name, evidence, labels, cards, judge))
        else:
            print(
                f"No vote: {len(voters)} model(s) passed, at least {MIN_VOTERS} are needed",
                file=sys.stderr,
            )
    print(format_agreement(results, args.threshold))
    path = save_results(results, args.threshold)
    print(f"Saved: {path}, {DEFAULT_DISAGREEMENTS}", file=sys.stderr)


def _assess(args: argparse.Namespace) -> None:
    """Every model over every contribution, one model at a time; the answers are saved."""
    github, taiga = collect(args)
    evidence = github.evidence + taiga.evidence
    cache = Cache()
    models = args.model or list(VOTERS)
    judges = {model: _judge(model, cache) for model in models}
    print(f"{len(evidence)} contributions, {len(models)} model(s)", file=sys.stderr)
    failed = run_models(evidence, load_cards(), judges, _progress)
    print(f"Saved answers: {cache.hits} reused, {cache.misses} new", file=sys.stderr)
    for model, count in failed.items():
        if count:
            print(f"  {model}: {count} contribution(s) without a usable answer", file=sys.stderr)


def _report(args: argparse.Namespace) -> None:
    """Check calibration, make sure every answer is saved, then write the reports."""
    models = args.model or list(VOTERS)
    if len(models) == 2:
        raise ValueError(f"Use one model or at least {MIN_VOTERS} for a vote, not two")
    name, agreement = calibrated(models, DEFAULT_RESULTS)  # stops here if not passed
    students = load_students(args.students, role_column=args.role)
    github, taiga = collect(args)
    evidence = github.evidence + taiga.evidence
    cards = load_cards()
    cache = Cache()
    judges = {model: _judge(model, cache) for model in models}
    run_models(evidence, cards, judges, _progress)  # new contributions only; the rest is saved
    judge = judges[models[0]] if len(models) == 1 else majority(list(judges.values()), name)
    assessments = {}
    for item in evidence:
        try:
            assessments[item.item_id] = judge(item, cards[item.kind])
        except ModelResponseError:
            continue  # no model could answer: left out of the reports
    method = models[0] if len(models) == 1 else f"{len(models)} modelin çoğunluk oyu"
    matches = match_students(students, github.users, github.emails, taiga.users)
    written = write_reports(
        matches, evidence, assessments, cards, args.period, method, agreement, args.out
    )
    print(f"Saved {len(written)} student reports and {SUMMARY_FILE} in {args.out}", file=sys.stderr)


def _progress(text: str) -> None:
    """One line per model, rewritten in place; a new line when the model is done."""
    done, total = text.rsplit(" ", 1)[1].split("/")
    print(f"\r{text}   ", end="\n" if done == total else "", file=sys.stderr, flush=True)


def _judge(model: str, cache: Cache) -> Judge:
    """One local model, with saved answers."""
    ask = ollama(model)
    return lambda evidence, card: assess_cached(evidence, card, ask, model, cache)


if __name__ == "__main__":
    sys.exit(main())
