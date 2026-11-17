# Ledger Lab

Offline CSV totals by category. Requires Python 3.12 and the standard library only. The program does not use the network.

## Usage

```text
python ledger.py input.csv
python ledger.py --month 2024-01 input.csv
python ledger.py input.csv --month 2024-02
python ledger.py input.csv --refunds
python ledger.py --refunds input.csv --month 2024-02
python ledger.py --month 2024-01 input.csv --refunds
```

`--month` may appear before or after the file. Its value must be `YYYY-MM` with a month from 01 to 12. The program still checks every row, including rows outside that month, and totals only the selected month. A month that matches no rows prints `{}`. A bad month value exits 1.

`--refunds` takes no value. It may appear before or after the file and in either order with `--month`. Repeating it exits 2 with the same usage line as any other bad invocation. With the flag, amounts may have one leading minus. Without it, a negative amount is invalid on every row, including a row outside the selected month. A category total of zero is `0.00`, never `-0.00`. A nonzero negative total keeps the minus and two fractional digits.

The file must start with this header, in this order:

```text
date,category,amount
```

A valid file prints one JSON object and exits 0. Keys are categories in Unicode code-point order. Values are strings with two fractional digits, summed with `decimal.Decimal`. Zero is normalized to `0.00`.

```text
date,category,amount
2024-01-02,food,10
2024-01-03,food,2.5
2024-01-01,cafe,1.25
```

```text
{"cafe": "1.25", "food": "12.50"}
```

A header with no data rows prints `{}`.

Invalid input, an unreadable file, or a bad encoding writes a message to stderr, exits 1, and prints nothing on stdout. The wrong number of arguments exits 2 and writes:

```text
Usage: python ledger.py input.csv
```

## API

`summarize_csv(text: str, month: str | None = None, allow_refunds: bool = False) -> dict[str, str]`

Same rules as the command-line program. `month=None` totals every valid row. A supplied month must match `YYYY-MM` exactly, even when the file has no data rows. Invalid text or an invalid month raises `ValueError`. `allow_refunds=False` rejects a leading minus. `allow_refunds=True` accepts one leading minus and still rejects every other amount format. Month filtering and refunds apply together: excluded rows are validated, then omitted.

## Rules

- Parse CSV with quoting. A quoted field may contain commas and doubled quotes.
- Dates are real calendar dates in exact `YYYY-MM-DD` form. `2024-02-29` is valid. `2023-02-29` is not.
- Trim outer whitespace on each data cell. A category must still be nonempty. Internal spaces and punctuation stay in the category name.
- Amounts are ordinary decimals with at most two fractional digits. Integers are allowed. A leading `-` is accepted only when refunds are enabled. Scientific notation, a leading `+`, and thousands separators are not.
- Every data row has exactly three cells. Blank lines are invalid.
- With `--month`, rows in other months are validated and then left out of the totals. A negative amount outside that month is still an error when refunds are off.

## Tests

```text
python -m unittest -v
```
