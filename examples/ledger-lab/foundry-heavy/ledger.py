import csv
import io
import json
import sys
import datetime
import decimal
import pathlib
import re


def summarize_csv(
    text: str, month: str | None = None, allow_refunds: bool = False
) -> dict[str, str]:
    if month is not None and re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) is None:
        raise ValueError(f"invalid month {month!r}")

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("missing header") from None
    expected = ["date", "category", "amount"]
    if header != expected:
        raise ValueError(f"invalid header: expected {expected!r}")

    totals: dict[str, decimal.Decimal] = {}
    for row_number, row in enumerate(reader, 1):
        if len(row) != 3:
            raise ValueError(
                f"data row {row_number}: expected exactly 3 cells, got {len(row)}"
            )
        date_text, category, amount_text = (cell.strip() for cell in row)
        if (
            len(date_text) != 10
            or date_text[4] != "-"
            or date_text[7] != "-"
            or not date_text[:4].isdigit()
            or not date_text[5:7].isdigit()
            or not date_text[8:].isdigit()
        ):
            raise ValueError(f"data row {row_number}: invalid date {date_text!r}")
        try:
            datetime.date.fromisoformat(date_text)
        except ValueError:
            raise ValueError(f"data row {row_number}: invalid date {date_text!r}") from None
        if not category:
            raise ValueError(f"data row {row_number}: category must be nonempty")

        negative = allow_refunds and amount_text.startswith("-")
        amount_body = amount_text[1:] if negative else amount_text
        if (
            not amount_body
            or not amount_body[0].isdigit()
            or (
                amount_body[0] == "0"
                and len(amount_body) > 1
                and amount_body[1] != "."
            )
            or any(char not in "0123456789." for char in amount_body)
            or amount_body.count(".") > 1
        ):
            raise ValueError(f"data row {row_number}: invalid amount {amount_text!r}")
        whole, dot, fraction = amount_body.partition(".")
        if (
            not whole
            or (dot and not 1 <= len(fraction) <= 2)
            or (whole != "0" and whole.startswith("0"))
        ):
            raise ValueError(f"data row {row_number}: invalid amount {amount_text!r}")
        try:
            amount = decimal.Decimal(amount_text)
        except decimal.InvalidOperation:
            raise ValueError(f"data row {row_number}: invalid amount {amount_text!r}") from None
        if month is None or date_text[:7] == month:
            totals[category] = totals.get(category, decimal.Decimal(0)) + amount

    result = {}
    for category, total in sorted(totals.items()):
        rounded = total.quantize(
            decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_EVEN
        )
        result[category] = "0.00" if rounded == 0 else format(rounded, "f")
    return result


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    tokens = args[1:]
    path = None
    month = None
    month_seen = False
    refunds = False
    refunds_seen = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--month":
            if month_seen or index + 1 >= len(tokens) or tokens[index + 1].startswith("-"):
                sys.stderr.write("Usage: python ledger.py input.csv\n")
                return 2
            month_seen = True
            month = tokens[index + 1]
            index += 2
        elif token == "--refunds":
            if refunds_seen:
                sys.stderr.write("Usage: python ledger.py input.csv\n")
                return 2
            refunds_seen = True
            refunds = True
            index += 1
        elif token.startswith("-"):
            sys.stderr.write("Usage: python ledger.py input.csv\n")
            return 2
        elif path is not None:
            sys.stderr.write("Usage: python ledger.py input.csv\n")
            return 2
        else:
            path = token
            index += 1

    if path is None:
        sys.stderr.write("Usage: python ledger.py input.csv\n")
        return 2
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"Error reading input: {exc}\n")
        return 1
    try:
        summary = summarize_csv(text, month=month, allow_refunds=refunds)
    except ValueError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())