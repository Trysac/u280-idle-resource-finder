"""Command-line interface for idle-resource-finder."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from idle_resource_finder import IdleError, Thresholds, find_idle, load_inventory, render


def _parse_datetime_arg(value: str | None) -> datetime:
    """Parse --now argument as RFC 3339, defaulting to timezone.utc."""
    if value is None:
        return datetime.now(timezone.utc)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid datetime: {value}") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise argparse.ArgumentTypeError(f"datetime must include timezone: {value}")
    return dt


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code 0/1/2."""
    parser = argparse.ArgumentParser(
        prog="idle-resource-finder",
        description="Find idle cloud resources in a JSON inventory.",
    )
    parser.add_argument("inventory", help="Path to inventory JSON file")
    parser.add_argument(
        "--now",
        type=_parse_datetime_arg,
        default=None,
        help="Current time as RFC 3339 with offset (default: now UTC)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--min-age-days",
        type=int,
        default=7,
        help="Minimum age in days for unattached volumes (default: 7)",
    )
    parser.add_argument(
        "--stopped-days",
        type=int,
        default=30,
        help="Minimum stopped days for stopped instances (default: 30)",
    )

    args = parser.parse_args(argv)

    try:
        inventory_path = Path(args.inventory)
        content = inventory_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as e:
        print(f"error reading inventory: {e}", file=sys.stderr)
        return 2

    try:
        resources = load_inventory(content)
    except IdleError as e:
        print(f"invalid inventory: {e}", file=sys.stderr)
        return 1

    thresholds = Thresholds(
        min_age_days=args.min_age_days,
        stopped_days=args.stopped_days,
    )
    now = args.now if args.now is not None else datetime.now(timezone.utc)

    report = find_idle(resources, now=now, thresholds=thresholds)
    output = render(report, fmt=args.format)
    print(output, end="")

    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
