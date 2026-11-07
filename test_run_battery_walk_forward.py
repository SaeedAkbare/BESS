"""Tests for chronological month enumeration and multi-month orchestration."""
import unittest
from unittest.mock import patch

from run_battery_walk_forward import months_between


class MultiMonthRunnerTests(unittest.TestCase):
    def test_year_boundary(self):
        self.assertEqual(months_between("2026-10", "2027-02"),
                         ["2026-10", "2026-11", "2026-12", "2027-01", "2027-02"])

    def test_single_month(self):
        self.assertEqual(months_between("2026-10", "2026-10"), ["2026-10"])

    def test_reverse_range_rejected(self):
        with self.assertRaises(ValueError):
            months_between("2027-01", "2026-12")

    def test_invalid_month_rejected(self):
        with self.assertRaises(ValueError):
            months_between("2026-13", "2027-01")


if __name__ == "__main__":
    unittest.main()
