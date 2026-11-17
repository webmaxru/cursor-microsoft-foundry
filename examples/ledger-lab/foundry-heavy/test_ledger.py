"""Tests for the offline CSV ledger."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import ledger

ROOT = Path(__file__).resolve().parent
HEADER = "date,category,amount\n"


def csv_text(*rows: str) -> str:
    return HEADER + "".join(row + "\n" for row in rows)


class SummarizeTests(unittest.TestCase):
    def test_normative_sums(self):
        text = csv_text("2024-01-02,food,10", "2024-01-03,food,2.5", "2024-01-01,cafe,1.25")
        self.assertEqual(
            ledger.summarize_csv(text),
            {"cafe": "1.25", "food": "12.50"},
        )

    def test_quoted_category_with_comma(self):
        text = csv_text(
            '2024-02-29," coffee, tea ",0.10',
            '2024-03-01," coffee, tea ",0.20',
        )
        self.assertEqual(ledger.summarize_csv(text), {"coffee, tea": "0.30"})

    def test_doubled_quotes_in_category(self):
        text = csv_text('2024-01-01,"say ""hi""",1')
        self.assertEqual(ledger.summarize_csv(text), {'say "hi"': "1.00"})

    def test_decimal_sum_not_binary_float(self):
        text = csv_text("2024-01-01,food,0.10", "2024-01-02,food,0.20")
        self.assertEqual(ledger.summarize_csv(text), {"food": "0.30"})

    def test_lone_zero(self):
        self.assertEqual(
            ledger.summarize_csv(csv_text("2024-01-01,food,0")),
            {"food": "0.00"},
        )

    def test_sort_order_is_unicode_code_point(self):
        text = csv_text("2024-01-01,a,1", "2024-01-01,B,2")
        summary = ledger.summarize_csv(text)
        self.assertEqual(list(summary), ["B", "a"])
        self.assertEqual(summary, {"B": "2.00", "a": "1.00"})

    def test_internal_spaces_kept(self):
        text = csv_text("2024-01-01,  a  b  ,1")
        self.assertEqual(ledger.summarize_csv(text), {"a  b": "1.00"})

    def test_header_only(self):
        self.assertEqual(ledger.summarize_csv(HEADER), {})
        self.assertEqual(ledger.summarize_csv("date,category,amount"), {})

    def test_empty_input(self):
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv("")
        self.assertIn("missing header", str(caught.exception))

    def test_header_must_match_exactly(self):
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(" date,category,amount\n")
        self.assertIn("invalid header", str(caught.exception))

    def test_short_row_reports_data_row_number(self):
        text = csv_text("2024-01-01,food,1.00", "2024-01-02,food")
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(text)
        message = str(caught.exception)
        self.assertIn("data row 2", message)
        self.assertIn("expected exactly 3 cells", message)

    def test_extra_cell_is_rejected(self):
        text = csv_text("2024-01-01,food,1.00,extra")
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(text)
        self.assertIn("data row 1", str(caught.exception))

    def test_blank_line_is_a_malformed_row(self):
        text = HEADER + "2024-01-01,food,1.00\n\n2024-01-03,cafe,1.00\n"
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(text)
        self.assertIn("data row 2", str(caught.exception))

    def test_leap_day_and_impossible_dates(self):
        accepted = ledger.summarize_csv(csv_text("2024-02-29,food,1"))
        self.assertEqual(accepted, {"food": "1.00"})
        for raw in ("2023-02-29", "2024-04-31", "2024/01/01"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError) as caught:
                    ledger.summarize_csv(csv_text(f"{raw},food,1"))
                message = str(caught.exception)
                self.assertIn("invalid date", message)
                self.assertIn("data row 1", message)
                self.assertIn(raw, message)

    def test_rejected_amounts(self):
        samples = ["-1", "+1", "00.50", "1.", ".5", "1.234", "1e2", "NaN", "Inf", "1,000"]
        for raw in samples:
            with self.subTest(raw=raw):
                cell = f'"{raw}"' if "," in raw else raw
                with self.assertRaises(ValueError) as caught:
                    ledger.summarize_csv(csv_text(f"2024-01-01,food,{cell}"))
                message = str(caught.exception)
                self.assertIn("invalid amount", message)
                self.assertIn("data row 1", message)

    def test_accepted_amounts(self):
        expected = {"0.5": "0.50", "0.50": "0.50", "10": "10.00", "10.5": "10.50"}
        for raw, total in expected.items():
            with self.subTest(raw=raw):
                summary = ledger.summarize_csv(csv_text(f"2024-01-01,food,{raw}"))
                self.assertEqual(summary, {"food": total})


class CliTests(unittest.TestCase):
    def run_main(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = ledger.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_usage_when_argument_count_is_wrong(self):
        for argv in (["ledger.py"], ["ledger.py", "a.csv", "b.csv"]):
            with self.subTest(argv=argv):
                code, stdout, stderr = self.run_main(argv)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, "Usage: python ledger.py input.csv\n")

    def test_success_prints_one_json_object(self):
        text = csv_text("2024-01-02,food,10", "2024-01-03,food,2.5", "2024-01-01,cafe,1.25")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(text, encoding="utf-8", newline="\n")
            code, stdout, stderr = self.run_main(["ledger.py", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout,
            json.dumps({"cafe": "1.25", "food": "12.50"}, ensure_ascii=False, sort_keys=True) + "\n",
        )

    def test_invalid_csv_has_no_stdout_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(csv_text("2023-02-29,food,1"), encoding="utf-8", newline="\n")
            code, stdout, stderr = self.run_main(["ledger.py", str(path)])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Error:", stderr)
        self.assertIn("2023-02-29", stderr)

    def test_missing_file_and_invalid_encoding(self):
        missing = self.run_main(["ledger.py", "no-such-ledger-file.csv"])
        self.assertEqual(missing[0], 1)
        self.assertEqual(missing[1], "")
        self.assertNotEqual(missing[2], "")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_bytes(b"\xff")
            code, stdout, stderr = self.run_main(["ledger.py", str(path)])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertNotEqual(stderr, "")

    def test_subprocess_cli(self):
        program = str(ROOT / "ledger.py")
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "good.csv"
            bad = Path(directory) / "bad.csv"
            good.write_text(
                csv_text("2024-01-01,café,1.5"),
                encoding="utf-8",
                newline="\n",
            )
            bad.write_text(csv_text("2024-01-01,food,1e2"), encoding="utf-8", newline="\n")
            success = subprocess.run(
                [sys.executable, program, str(good)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            failure = subprocess.run(
                [sys.executable, program, str(bad)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            usage = subprocess.run(
                [sys.executable, program],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        self.assertEqual(success.returncode, 0)
        self.assertEqual(success.stderr, "")
        self.assertEqual(success.stdout, '{"café": "1.50"}\n')
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(failure.stdout, "")
        self.assertIn("invalid amount", failure.stderr)
        self.assertEqual(usage.returncode, 2)
        self.assertEqual(usage.stdout, "")
        self.assertIn("Usage: python ledger.py input.csv", usage.stderr)


SAMPLE = csv_text(
    "2024-01-02,food,10",
    "2024-01-03,food,2.5",
    "2024-02-01,cafe,1.25",
    "2024-02-02,food,1",
)


class MonthTests(unittest.TestCase):
    def run_main(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = ledger.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_january_total_and_unfiltered_sum(self):
        self.assertEqual(ledger.summarize_csv(SAMPLE, month="2024-01"), {"food": "12.50"})
        self.assertEqual(
            ledger.summarize_csv(SAMPLE),
            {"cafe": "1.25", "food": "13.50"},
        )

    def test_month_with_no_matching_rows(self):
        self.assertEqual(ledger.summarize_csv(SAMPLE, month="2024-03"), {})

    def test_excluded_invalid_date_still_errors(self):
        text = SAMPLE + "2024-13-01,food,1\n"
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(text, month="2024-01")
        message = str(caught.exception)
        self.assertIn("invalid date", message)
        self.assertIn("data row 5", message)

    def test_header_only_valid_month(self):
        self.assertEqual(ledger.summarize_csv(HEADER, month="2024-01"), {})

    def test_header_only_bad_month(self):
        for month in ("2024-1", "2024-13", "2024-00", "2024/02", " 2024-02", ""):
            with self.subTest(month=month):
                with self.assertRaises(ValueError) as caught:
                    ledger.summarize_csv(HEADER, month=month)
                self.assertIn("invalid month", str(caught.exception))

    def write_sample(self, directory):
        path = Path(directory) / "input.csv"
        path.write_text(SAMPLE, encoding="utf-8", newline="\n")
        return path

    def test_month_flag_before_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_sample(directory)
            code, stdout, stderr = self.run_main(["ledger.py", "--month", "2024-01", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, '{"food": "12.50"}\n')

    def test_month_flag_after_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_sample(directory)
            code, stdout, stderr = self.run_main(["ledger.py", str(path), "--month", "2024-02"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, '{"cafe": "1.25", "food": "1.00"}\n')

    def test_duplicate_month_flag_is_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_sample(directory)
            code, stdout, stderr = self.run_main(
                ["ledger.py", "--month", "2024-01", "--month", "2024-02", str(path)]
            )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Usage: python ledger.py input.csv\n")

    def test_invalid_month_value_exits_without_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_sample(directory)
            code, stdout, stderr = self.run_main(["ledger.py", "--month", "2024-13", str(path)])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("invalid month", stderr)


REFUND_SAMPLE = csv_text(
    "2024-01-02,food,10",
    "2024-01-03,food,-2.50",
    "2024-02-01,cafe,-1.25",
    "2024-02-02,food,1",
)


class RefundTests(unittest.TestCase):
    def run_main(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = ledger.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_refunds_off_rejects_negative(self):
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(csv_text("2024-01-02,food,-1"))
        self.assertIn("invalid amount", str(caught.exception))

    def test_refunds_on_mixed_month_none(self):
        self.assertEqual(
            ledger.summarize_csv(REFUND_SAMPLE, allow_refunds=True),
            {"cafe": "-1.25", "food": "8.50"},
        )

    def test_refunds_on_month_filter_january(self):
        self.assertEqual(
            ledger.summarize_csv(REFUND_SAMPLE, month="2024-01", allow_refunds=True),
            {"food": "7.50"},
        )

    def test_refunds_on_month_filter_february(self):
        self.assertEqual(
            ledger.summarize_csv(REFUND_SAMPLE, month="2024-02", allow_refunds=True),
            {"cafe": "-1.25", "food": "1.00"},
        )

    def test_signed_zero_normalized(self):
        text = csv_text("2024-01-01,food,1.00", "2024-01-02,food,-1.00")
        self.assertEqual(
            ledger.summarize_csv(text, allow_refunds=True),
            {"food": "0.00"},
        )

    def test_negative_zero_literal(self):
        self.assertEqual(
            ledger.summarize_csv(csv_text("2024-01-01,food,-0.00"), allow_refunds=True),
            {"food": "0.00"},
        )

    def test_strict_rejected_amount_fraction(self):
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(csv_text("2024-01-01,food,-1.001"), allow_refunds=True)
        self.assertIn("invalid amount", str(caught.exception))

    def test_out_of_month_negative_still_validated(self):
        text = csv_text("2024-01-01,food,5", "2024-02-01,food,-00.50")
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(text, month="2024-01", allow_refunds=False)
        self.assertIn("invalid amount", str(caught.exception))

    def test_invalid_month_precedes_refund_flag(self):
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(HEADER, month="2024-13", allow_refunds=True)
        self.assertIn("invalid month", str(caught.exception))

    def test_cli_refunds_placement_and_month(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(REFUND_SAMPLE, encoding="utf-8", newline="\n")
            code, stdout, stderr = self.run_main(
                ["ledger.py", "--refunds", str(path), "--month", "2024-02"]
            )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, '{"cafe": "-1.25", "food": "1.00"}\n')

    def test_duplicate_refunds_flag_is_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(REFUND_SAMPLE, encoding="utf-8", newline="\n")
            code, stdout, stderr = self.run_main(
                ["ledger.py", "--refunds", "--refunds", str(path)]
            )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Usage: python ledger.py input.csv\n")


if __name__ == "__main__":
    unittest.main()
