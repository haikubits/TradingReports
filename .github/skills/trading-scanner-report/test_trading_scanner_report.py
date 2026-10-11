from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).with_name("trading_scanner_report.py")
spec = importlib.util.spec_from_file_location("trading_scanner_report", SCRIPT)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class PreviousSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        daily_index = pd.date_range("2026-10-08", periods=2, freq="D", tz="America/New_York")
        self.daily = pd.DataFrame(
            {
                "Open": [100.0, 100.0],
                "High": [101.0, 102.0],
                "Low": [99.0, 98.0],
                "Close": [100.0, 100.0],
                "Volume": [1000, 1000],
            },
            index=daily_index,
        )
        hourly_index = pd.DatetimeIndex(
            ["2026-10-09 08:00:00", "2026-10-09 10:00:00"], tz="America/New_York"
        )
        self.hourly = pd.DataFrame(
            {"High": [101.0, 103.0], "Low": [99.0, 97.0], "Close": [100.0, 100.0]},
            index=hourly_index,
        )

    def test_previous_session_is_last_completed_candle(self) -> None:
        ntz = scanner.compute_ntz(self.daily, self.hourly)
        self.assertEqual((ntz["yd_high"], ntz["yd_low"]), (102.0, 98.0))
        self.assertEqual((ntz["pm_high"], ntz["pm_low"]), (101.0, 99.0))
        levels = scanner.compute_levels(self.hourly, self.daily, 100.0, ntz)
        self.assertEqual(len(levels["up"]), 3)
        self.assertEqual(len(levels["down"]), 3)
        self.assertTrue(any("Previous Session High" in level["sources"] for level in levels["up"]))
        self.assertTrue(any("Previous Session Low" in level["sources"] for level in levels["down"]))
        self.assertTrue(any("Prior Pre-market High" in level["sources"] for level in levels["up"]))

    def test_html_has_no_whitespace_only_line_without_failures(self) -> None:
        report = {
            "economic_events": [],
            "fed_speakers": [],
            "vix_regime": "low",
            "vix": 14.8,
            "spy_trend": "Range",
            "spy_sma_pos": "Above",
            "avg_conviction": 79,
            "scanned_count": 10,
            "passed_count": 8,
            "top_picks": [],
            "failures": [],
            "session_date": "Monday, October 12, 2026",
            "generated_at": "Saturday 11:05 PM ET",
        }
        html = scanner.generate_html(report)
        self.assertFalse(any(line and not line.strip() for line in html.splitlines()))
        self.assertIn("Monday, October 12, 2026", html)


if __name__ == "__main__":
    unittest.main()
