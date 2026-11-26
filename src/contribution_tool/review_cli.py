"""Command line for the qualitative review (REQ-7)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contribution_tool.cards import load_cards
from contribution_tool.cli import add_source_arguments, check_dates, collect
from contribution_tool.review.agreement import (
    CANDIDATES,
    DEFAULT_DISAGREEMENTS,
    DEFAULT_THRESHOLD,
    evidence_from_sheet,
    format_agreement,
    measure,
    save_results,
)
from contribution_tool.review.cache import Cache
from contribution_tool.review.calibration import (
    DEFAULT_SHEET,
    PER_KIND,
    choose_sample,
    load_labels,
    write_label_sheet,
)
from contribution_tool.review.llm import ollama


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

    args = parser.parse_args(argv)
    if args.command == "sheet":
        check_dates(sheet, args)
    elif not 0 < args.threshold <= 1:
        calibrate.error("--threshold must be between 0 and 1, e.g. 0.8")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "sheet":
            _sheet(args)
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
    results = []
    for model in args.model or CANDIDATES:
        print(f"Asking {model} ({len(labels)} labels)...", file=sys.stderr)
        results.append(measure(model, evidence, labels, cards, ollama(model), cache))
    print(format_agreement(results, args.threshold))
    path = save_results(results, args.threshold)
    print(f"Saved: {path}, {DEFAULT_DISAGREEMENTS}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
