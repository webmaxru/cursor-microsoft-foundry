"""Offline category totals for a simple expense ledger CSV."""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date
from decimal import Decimal
from io import StringIO

_HEADER = ["date", "category", "amount"]
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")
_AMOUNT = re.compile(r"^\d+(?:\.\d{1,2})?$")
_REFUND_AMOUNT = re.compile(r"^-?\d+(?:\.\d{1,2})?$")
_USAGE = "usage: python ledger.py input.csv [--month YYYY-MM] [--refunds]"


def summarize_csv(
    text: str,
    month: str | None = None,
    allow_refunds: bool = False,
) -> dict[str, str]:
    """Sum amount by category, optionally limited to one calendar month.

    The result maps each trimmed category to a two-decimal total. Categories
    are sorted alphabetically. Header-only input returns an empty dict.
    Every data row is validated, including rows outside ``month``.
    Negative amounts are accepted only when ``allow_refunds`` is true.
    A total of zero is always ``"0.00"``.
    """
    selected = _parse_month(month)
    if not isinstance(text, str):
        raise ValueError("CSV input must be a string")

    try:
        rows = list(csv.reader(StringIO(text), strict=True))
    except csv.Error as exc:
        raise ValueError(f"malformed CSV: {exc}") from exc

    if not rows:
        raise ValueError("missing header row; expected date,category,amount")

    header = rows[0]
    if header != _HEADER:
        raise ValueError(
            f"invalid header {header!r}; expected exactly date,category,amount"
        )

    totals: dict[str, Decimal] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != 3:
            raise ValueError(
                f"row {row_number}: expected 3 fields (date,category,amount), "
                f"found {len(row)}"
            )
        raw_date, raw_category, raw_amount = row
        parsed_date = _parse_date(raw_date, row_number)
        category = _parse_category(raw_category, row_number)
        amount = _parse_amount(raw_amount, row_number, allow_refunds=allow_refunds)
        if selected is not None and parsed_date.strftime("%Y-%m") != selected:
            continue
        if category in totals:
            totals[category] += amount
        else:
            totals[category] = amount

    return {category: _format_total(totals[category]) for category in sorted(totals)}


def _parse_month(month: str | None) -> str | None:
    if month is None:
        return None
    if not isinstance(month, str) or not _MONTH.fullmatch(month):
        raise ValueError(
            f"invalid month {month!r}; expected YYYY-MM with month 01..12"
        )
    return month


def _parse_date(value: str, row_number: int) -> date:
    if not _DATE.fullmatch(value):
        raise ValueError(
            f"row {row_number}: invalid date {value!r}; expected YYYY-MM-DD"
        )
    year, month, day = (int(part) for part in value.split("-"))
    try:
        return date(year, month, day)
    except ValueError:
        raise ValueError(
            f"row {row_number}: invalid date {value!r}; not a real calendar date"
        ) from None


def _parse_category(value: str, row_number: int) -> str:
    category = value.strip()
    if not category:
        raise ValueError(
            f"row {row_number}: category must be nonempty after trimming"
        )
    return category


def _parse_amount(value: str, row_number: int, allow_refunds: bool = False) -> Decimal:
    text = value.strip()
    pattern = _REFUND_AMOUNT if allow_refunds else _AMOUNT
    if not pattern.fullmatch(text):
        if allow_refunds:
            expected = (
                "an ordinary decimal with an optional leading minus and "
                "at most two fractional digits"
            )
        else:
            expected = "a nonnegative ordinary decimal with at most two fractional digits"
        raise ValueError(
            f"row {row_number}: invalid amount {value!r}; expected {expected}"
        )
    amount = Decimal(text)
    if not amount.is_finite() or (not allow_refunds and amount < 0):
        kind = "a finite amount" if allow_refunds else "a nonnegative finite amount"
        raise ValueError(
            f"row {row_number}: invalid amount {value!r}; expected {kind}"
        )
    return amount


def _format_total(amount: Decimal) -> str:
    """Render a category total with two decimals and an unsigned zero."""
    quantized = amount.quantize(Decimal("0.01"))
    if quantized.is_zero():
        return "0.00"
    return f"{quantized:.2f}"


def _parse_cli(args: list[str]) -> tuple[str, str | None, bool]:
    path: str | None = None
    month: str | None = None
    allow_refunds = False
    seen_month = False
    seen_refunds = False
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--month":
            if seen_month:
                raise ValueError("--month supplied more than once")
            if index + 1 >= len(args):
                raise ValueError("--month requires a YYYY-MM value")
            seen_month = True
            month = args[index + 1]
            index += 2
            continue
        if arg == "--refunds":
            if seen_refunds:
                raise ValueError("--refunds supplied more than once")
            seen_refunds = True
            allow_refunds = True
            index += 1
            continue
        if arg.startswith("-"):
            raise ValueError(f"unknown option {arg}")
        if path is not None:
            raise ValueError(f"unexpected argument {arg}")
        path = arg
        index += 1
    if path is None:
        raise ValueError("missing input.csv")
    return path, month, allow_refunds


def main(argv: list[str] | None = None) -> int:
    """Print a JSON summary for one CSV file, or report an error on stderr."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(_USAGE, file=sys.stderr)
        return 2
    try:
        path, month, allow_refunds = _parse_cli(args)
    except ValueError as exc:
        print(_USAGE, file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError:
        print(f"error: {path} is not valid UTF-8 text", file=sys.stderr)
        return 1
    except OSError as exc:
        detail = exc.strerror or str(exc)
        print(f"error: cannot read {path}: {detail}", file=sys.stderr)
        return 1

    try:
        summary = summarize_csv(text, month=month, allow_refunds=allow_refunds)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(json.dumps(summary) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
