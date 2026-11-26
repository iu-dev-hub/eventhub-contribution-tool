"""Command line for the qualitative review (REQ-7)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contribution_tool.cards import load_cards
from contribution_tool.cli import add_source_arguments, check_dates, collect
from contribution_tool.review.calibration import (
    DEFAULT_SHEET,
    PER_KIND,
    choose_sample,
    write_label_sheet,
)


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
    args = parser.parse_args(argv)
    check_dates(sheet, args)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        github, taiga = collect(args)
        sample = choose_sample(github.evidence + taiga.evidence, args.per_kind)
        path = write_label_sheet(sample, load_cards(), args.out)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Saved {len(sample)} contributions for labelling: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
