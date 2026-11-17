"""Independent acceptance checks for the synthetic Ledger Lab experiment."""

import argparse
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT = None
STAGE = 1


class LedgerAcceptance(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("ledger_under_test", PROJECT / "ledger.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def summarize(self, rows, **kwargs):
        return self.module.summarize_csv("date,category,amount\n" + rows, **kwargs)

    def test_exact_money_and_sorted_categories(self):
        result = self.summarize("2026-01-01,z,0.10\n2026-01-02,z,0.20\n2026-01-02,a,12\n")
        self.assertEqual(result, {"a": "12.00", "z": "0.30"})
        self.assertEqual(list(result), ["a", "z"])

    def test_empty_and_quoted_categories(self):
        self.assertEqual(self.summarize(""), {})
        self.assertEqual(self.summarize('2026-02-28,"food, home",2.50\n'), {"food, home": "2.50"})

    def test_invalid_money(self):
        for value in ("-1", "NaN", "Infinity", "1.001", "1e2", "abc", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.summarize(f"2026-01-01,x,{value}\n")

    def test_invalid_date_category_and_shape(self):
        for row in ("2026-02-30,x,1\n", "2026-1-01,x,1\n", "2026-01-01, ,1\n",
                    "2026-01-01,x\n", "2026-01-01,x,1,extra\n"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.summarize(row)
        with self.assertRaises(ValueError):
            self.module.summarize_csv("date,amount\n2026-01-01,1\n")

    def test_cli_json_and_errors(self):
        fixture = PROJECT / "acceptance-input.csv"
        fixture.write_text("date,category,amount\n2026-01-01,food,1.20\n", encoding="utf-8")
        try:
            result = subprocess.run([sys.executable, str(PROJECT / "ledger.py"), str(fixture)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"food": "1.20"})
            fixture.write_text("date,category,amount\n2026-02-30,x,1\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(PROJECT / "ledger.py"), str(fixture)],
                                    capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
            self.assertFalse(result.stdout.strip())
        finally:
            fixture.unlink(missing_ok=True)

    def test_month_filter(self):
        if STAGE < 2:
            self.skipTest("Introduced in stage 2")
        self.assertEqual(self.summarize("2026-01-01,x,1\n2026-02-01,x,2\n", month="2026-02"),
                         {"x": "2.00"})
        for month in ("2026-13", "2026-1", "bad"):
            with self.subTest(month=month), self.assertRaises(ValueError):
                self.summarize("", month=month)

    def test_filter_does_not_hide_invalid_records(self):
        if STAGE < 2:
            self.skipTest("Introduced in stage 2")
        with self.assertRaises(ValueError):
            self.summarize("2026-01-01,x,NaN\n", month="2026-02")

    def test_refunds_and_retained_contract(self):
        if STAGE < 3:
            self.skipTest("Introduced in stage 3")
        self.assertEqual(self.summarize("2026-01-01,x,2\n2026-01-02,x,-2.50\n",
                                        allow_refunds=True), {"x": "-0.50"})
        self.assertEqual(self.summarize("2026-01-01,x,-0.00\n", allow_refunds=True), {"x": "0.00"})
        with self.assertRaises(ValueError):
            self.summarize("2026-01-01,x,-1.001\n", allow_refunds=True)

    def test_combined_cli_options(self):
        if STAGE < 3:
            self.skipTest("Introduced in stage 3")
        fixture = PROJECT / "acceptance-input.csv"
        fixture.write_text("date,category,amount\n2026-01-01,x,7\n2026-02-01,x,-1.20\n",
                           encoding="utf-8")
        try:
            result = subprocess.run([sys.executable, str(PROJECT / "ledger.py"), str(fixture),
                                     "--month", "2026-02", "--refunds"],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"x": "-1.20"})
        finally:
            fixture.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--stage", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    PROJECT, STAGE = args.project.resolve(), args.stage
    unittest.main(argv=[sys.argv[0]], verbosity=2)
