"""Tests for Ledger Lab category summaries."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import ledger

HEADER = "date,category,amount\n"
ROOT = Path(__file__).resolve().parent


class SummarizeCsvTests(unittest.TestCase):
    def test_header_only_is_empty(self):
        self.assertEqual(ledger.summarize_csv(HEADER), {})
        self.assertEqual(ledger.summarize_csv("date,category,amount"), {})

    def test_sums_with_decimal_and_sorts_categories(self):
        text = (
            HEADER
            + "2026-01-01,z,0.10\n"
            + "2026-01-02,z,0.20\n"
            + "2026-01-02,a,12\n"
        )
        result = ledger.summarize_csv(text)
        self.assertEqual(result, {"a": "12.00", "z": "0.30"})
        self.assertEqual(list(result), ["a", "z"])

    def test_quoted_category_keeps_comma_and_punctuation(self):
        text = HEADER + '2026-02-28,"food, home",2.50\n2026-03-01,"well-being: a/b",1\n'
        self.assertEqual(
            ledger.summarize_csv(text),
            {"food, home": "2.50", "well-being: a/b": "1.00"},
        )

    def test_trims_category_and_merges_matches(self):
        text = HEADER + "2026-04-01,  snacks ,1.5\n2026-04-02,snacks,0.25\n"
        self.assertEqual(ledger.summarize_csv(text), {"snacks": "1.75"})

    def test_accepts_leap_day_and_one_decimal_place(self):
        text = HEADER + "2024-02-29,rent,10.5\n"
        self.assertEqual(ledger.summarize_csv(text), {"rent": "10.50"})

    def test_rejects_invalid_amounts(self):
        for value in ("-1", "NaN", "Infinity", "1.001", "1e2", "1E-1", "abc", "", "+2", "1."):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    ledger.summarize_csv(f"{HEADER}2026-01-01,x,{value}\n")
                self.assertIn("amount", str(caught.exception))

    def test_rejects_invalid_dates_categories_and_shape(self):
        rows = (
            "2026-02-30,x,1\n",
            "2026-02-29,x,1\n",
            "2026-1-01,x,1\n",
            "2026-01-01, ,1\n",
            "2026-01-01,   ,1\n",
            "2026-01-01,x\n",
            "2026-01-01,x,1,extra\n",
            "\n",
        )
        for row in rows:
            with self.subTest(row=row):
                with self.assertRaises(ValueError) as caught:
                    ledger.summarize_csv(HEADER + row)
                self.assertTrue(str(caught.exception).strip())

    def test_rejects_wrong_or_missing_header(self):
        for text in ("", "date,amount\n2026-01-01,1\n", "amount,category,date\n"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as caught:
                    ledger.summarize_csv(text)
                self.assertIn("header", str(caught.exception))

    def test_rejects_malformed_quotes(self):
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(HEADER + '2026-01-01,"open,1.00\n')
        self.assertIn("malformed CSV", str(caught.exception))

    def test_month_filter_keeps_exact_totals(self):
        text = HEADER + "2026-01-01,x,1\n2026-02-01,x,2\n2026-02-03,a,0.10\n"
        result = ledger.summarize_csv(text, month="2026-02")
        self.assertEqual(result, {"a": "0.10", "x": "2.00"})
        self.assertEqual(list(result), ["a", "x"])
        self.assertEqual(ledger.summarize_csv(HEADER, month="2026-02"), {})

    def test_month_must_be_exact_even_without_rows(self):
        for month in ("2026-13", "2026-1", "bad", "2026-00", "2026-01-01", ""):
            with self.subTest(month=month):
                with self.assertRaises(ValueError) as caught:
                    ledger.summarize_csv(HEADER, month=month)
                self.assertIn("month", str(caught.exception))

    def test_month_filter_still_validates_excluded_rows(self):
        text = HEADER + "2026-01-01,x,NaN\n2026-02-01,x,2\n"
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(text, month="2026-02")
        self.assertIn("amount", str(caught.exception))

    def test_refunds_sum_exact_totals_and_unsigned_zero(self):
        text = (
            HEADER
            + "2026-05-01,z,0.10\n"
            + "2026-05-01,z,0.20\n"
            + "2026-05-02,z,-0.30\n"
            + "2026-05-03,a,10\n"
            + "2026-05-04,a,-1.50\n"
            + "2026-05-05,m,-0.00\n"
            + "2026-05-06,m,-0\n"
        )
        result = ledger.summarize_csv(text, allow_refunds=True)
        self.assertEqual(result, {"a": "8.50", "m": "0.00", "z": "0.00"})
        self.assertEqual(list(result), ["a", "m", "z"])
        self.assertTrue(all(value != "-0.00" for value in result.values()))

    def test_refunds_keep_strict_amount_format(self):
        for value in (
            "-1.001",
            "--1",
            "-.5",
            "-1.",
            "+-1",
            "+2",
            "1e2",
            "-NaN",
            "-Infinity",
            " - ",
            "-",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    ledger.summarize_csv(
                        f"{HEADER}2026-01-01,x,{value}\n",
                        allow_refunds=True,
                    )
                self.assertIn("amount", str(caught.exception))

    def test_month_and_refunds_filter_after_full_validation(self):
        text = (
            HEADER
            + "2026-01-15,food,-4.00\n"
            + "2026-02-01,food,2.00\n"
            + "2026-02-02,food,-2.00\n"
            + "2026-02-03,  travel ,-0.40\n"
            + "2026-02-04,travel,0.40\n"
            + "2026-03-01,food,-100.00\n"
            + "2026-02-05,rent,-3.25\n"
        )
        blocked = HEADER + "2026-01-01,food,-1.00\n2026-02-01,food,3\n"
        with self.assertRaises(ValueError) as caught:
            ledger.summarize_csv(blocked, month="2026-02", allow_refunds=False)
        self.assertIn("amount", str(caught.exception))

        invalid_outside = HEADER + "2026-01-01,food,-1.234\n2026-02-01,food,-2.00\n"
        with self.assertRaises(ValueError) as outside:
            ledger.summarize_csv(invalid_outside, month="2026-02", allow_refunds=True)
        self.assertIn("amount", str(outside.exception))

        result = ledger.summarize_csv(text, month="2026-02", allow_refunds=True)
        self.assertEqual(result, {"food": "0.00", "rent": "-3.25", "travel": "0.00"})
        self.assertEqual(list(result), ["food", "rent", "travel"])
        self.assertTrue(all(value != "-0.00" for value in result.values()))
        self.assertEqual(ledger.summarize_csv(HEADER, month="2026-02", allow_refunds=True), {})


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "ledger.py"), *args],
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_prints_json_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text(HEADER + "2026-01-01,food,1.20\n", encoding="utf-8")
            result = self.run_cli(str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), {"food": "1.20"})

    def test_invalid_csv_has_stderr_and_no_stdout_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text(HEADER + "2026-02-30,x,1\n", encoding="utf-8")
            result = self.run_cli(str(path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("calendar date", result.stderr)
        self.assertFalse(result.stdout.strip())

    def test_missing_file_and_usage(self):
        missing = self.run_cli("no-such-ledger.csv")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("cannot read", missing.stderr)
        self.assertFalse(missing.stdout.strip())

        usage = self.run_cli()
        self.assertNotEqual(usage.returncode, 0)
        self.assertIn("usage:", usage.stderr)
        self.assertFalse(usage.stdout.strip())

    def test_month_option_filters_and_rejects_bad_months(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text(
                HEADER + "2026-01-01,x,1\n2026-02-01,x,2\n",
                encoding="utf-8",
            )
            filtered = self.run_cli(str(path), "--month", "2026-02")
            self.assertEqual(filtered.returncode, 0, filtered.stderr)
            self.assertEqual(json.loads(filtered.stdout), {"x": "2.00"})

            invalid_month = self.run_cli(str(path), "--month", "2026-13")
            self.assertNotEqual(invalid_month.returncode, 0)
            self.assertIn("month", invalid_month.stderr)
            self.assertFalse(invalid_month.stdout.strip())

            path.write_text(HEADER + "2026-01-01,x,NaN\n", encoding="utf-8")
            invalid_row = self.run_cli(str(path), "--month", "2026-02")
            self.assertNotEqual(invalid_row.returncode, 0)
            self.assertIn("amount", invalid_row.stderr)
            self.assertFalse(invalid_row.stdout.strip())

    def test_refunds_option_combines_with_month(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text(
                HEADER
                + "2026-01-01,food,5.00\n"
                + "2026-02-01,food,1.10\n"
                + "2026-02-02,food,-0.10\n"
                + "2026-02-03,a,-0.00\n"
                + "2026-03-01,food,-9.00\n",
                encoding="utf-8",
            )
            denied = self.run_cli(str(path), "--month", "2026-02")
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("amount", denied.stderr)
            self.assertFalse(denied.stdout.strip())

            allowed = self.run_cli("--refunds", str(path), "--month", "2026-02")
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(allowed.stderr, "")
            self.assertEqual(json.loads(allowed.stdout), {"a": "0.00", "food": "1.00"})

            repeated = self.run_cli(str(path), "--refunds", "--refunds")
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("--refunds", repeated.stderr)
            self.assertFalse(repeated.stdout.strip())

        usage = self.run_cli()
        self.assertIn("--refunds", usage.stderr)


if __name__ == "__main__":
    unittest.main()
