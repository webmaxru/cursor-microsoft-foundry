# Ledger Lab

Offline summaries of a CSV expense ledger. Python 3.12 standard library only. The program does not use the network.

## Usage

```bash
python ledger.py input.csv
python ledger.py input.csv --month 2026-02
python ledger.py input.csv --refunds
python ledger.py input.csv --month 2026-02 --refunds
```

The command prints one JSON object. Each key is a category and each value is that category's total with two decimal places. Categories are sorted alphabetically (Unicode code-point order). A total of zero is always `0.00`, never `-0.00`.

`--month` limits the totals to one calendar month. The value must be exact `YYYY-MM`, with the month from `01` through `12`. That check applies even when the file has no data rows. Every data row is still validated, including rows outside the selected month.

`--refunds` allows a leading minus on amounts. Without it, a negative amount is invalid in every row, including rows outside the selected month. The flag takes no value. Repeating it is an error. It can be combined with `--month` in either order.

Invalid input writes a message to stderr and exits nonzero. Stdout stays empty, so a failed run never emits partial JSON.

```text
usage: python ledger.py input.csv [--month YYYY-MM] [--refunds]
```

## CSV contract

The header row must be exactly `date,category,amount`, in that order.

| Column | Rule |
| --- | --- |
| date | A real calendar date in exact `YYYY-MM-DD` form. `2026-02-30` and `2026-1-01` are rejected. |
| category | Nonempty after surrounding whitespace is removed. Internal spaces and punctuation are kept. Standard CSV quoting is supported. |
| amount | Ordinary decimal notation: digits, with an optional `.` and one or two fractional digits. Integers are accepted. A leading `-` is accepted only when refunds are enabled. Scientific notation, a leading `+`, and values such as `NaN` or `Infinity` are rejected. |

Rows must have exactly those three fields. Totals are summed with `decimal.Decimal`. A file that contains only the header returns `{}`.

## API

```python
from ledger import summarize_csv

summarize_csv(
    text: str,
    month: str | None = None,
    allow_refunds: bool = False,
) -> dict[str, str]
```

`summarize_csv` raises `ValueError` with a row-specific message when the CSV is invalid. An invalid `month` also raises `ValueError`. `month=None` keeps every valid row. `allow_refunds=False` rejects negative amounts. `allow_refunds=True` accepts a leading minus and still rejects every other amount format. Month filtering and refunds apply together: excluded rows are validated, then omitted from the sorted totals.

## Tests

```bash
python -m unittest -v
```
