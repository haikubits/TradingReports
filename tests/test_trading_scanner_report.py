import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / ".github/skills/trading-scanner-report/trading_scanner_report.py"
spec = importlib.util.spec_from_file_location("trading_scanner_report", SCRIPT)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)
ET = ZoneInfo("America/New_York")


class NextSessionLevelsTests(unittest.TestCase):
    def setUp(self):
        self.daily = pd.DataFrame(
            {"High": [101.0, 105.0], "Low": [90.0, 95.0], "Close": [97.0, 100.0]},
            index=pd.to_datetime(["2026-11-05", "2026-11-06"]).tz_localize(ET),
        )
        self.session = datetime(2026, 11, 9, 9, 30, tzinfo=ET)

    def test_friday_data_does_not_become_monday_premarket(self):
        friday = pd.DataFrame(
            {"High": [103.0], "Low": [92.0], "Close": [98.0]},
            index=pd.to_datetime(["2026-11-06 08:00"]).tz_localize(ET),
        )
        ntz = scanner.compute_ntz(self.daily, friday, self.session, datetime(2026, 11, 6, 22, 0, tzinfo=ET))
        self.assertEqual((ntz["yd_high"], ntz["yd_low"]), (105.0, 95.0))
        self.assertIsNone(ntz["pm_high"])
        self.assertIsNone(ntz["pm_low"])
        self.assertEqual((ntz["ntz_upper"], ntz["ntz_lower"]), (105.0, 95.0))
        self.assertIn("pending", scanner.ntz_comment({"ntz": ntz, "price": 100.0}))
        levels = scanner.compute_levels(friday, self.daily, 100.0, ntz)
        self.assertTrue(all("Pre-market" not in source for side in ("up", "down") for level in levels[side] for source in level["sources"]))
        self.assertTrue(all(len(levels[side]) == 3 for side in ("up", "down")))
        self.assertTrue(all(level["confidence"] < 35 for side in ("up", "down") for level in levels[side] if "ATR Projection" in level["sources"]))
        pending = scanner.render_ntz({"ntz": ntz, "ntz_comment": "Next-session premarket pending"})
        self.assertIn("PM High</div><div class=\"price\">Pending", pending)

    def test_monday_premarket_is_used_when_available(self):
        monday = pd.DataFrame(
            {"High": [108.0, 130.0], "Low": [94.0, 70.0], "Close": [99.0, 100.0]},
            index=pd.to_datetime(["2026-11-09 08:00", "2026-11-09 09:00"]).tz_localize(ET),
        )
        ntz = scanner.compute_ntz(self.daily, monday, self.session, datetime(2026, 11, 9, 8, 0, tzinfo=ET))
        self.assertEqual((ntz["pm_high"], ntz["pm_low"]), (108.0, 94.0))
        self.assertEqual((ntz["ntz_upper"], ntz["ntz_lower"]), (108.0, 94.0))

    def test_pre_open_targets_today_and_after_open_targets_tomorrow(self):
        self.assertEqual(scanner.next_trading_day(datetime(2026, 11, 6, 22, 0, tzinfo=ET)).date(), self.session.date())
        self.assertEqual(scanner.next_trading_day(datetime(2026, 11, 9, 8, 0, tzinfo=ET)).date(), self.session.date())
        self.assertEqual(scanner.next_trading_day(datetime(2026, 11, 9, 10, 0, tzinfo=ET)).date(), datetime(2026, 11, 10).date())

    def test_in_progress_daily_candle_is_not_previous_session(self):
        monday_partial = pd.DataFrame(
            {"High": [120.0], "Low": [80.0], "Close": [100.0]},
            index=pd.to_datetime(["2026-11-09"]).tz_localize(ET),
        )
        daily = pd.concat([self.daily, monday_partial])
        tuesday = datetime(2026, 11, 10, 9, 30, tzinfo=ET)
        before_close = datetime(2026, 11, 9, 10, 0, tzinfo=ET)
        after_close = datetime(2026, 11, 9, 17, 0, tzinfo=ET)
        self.assertEqual(len(scanner.completed_daily(daily, before_close)), 2)
        self.assertEqual(len(scanner.completed_daily(daily, after_close)), 3)
        ntz = scanner.compute_ntz(daily, pd.DataFrame(), tuesday, before_close)
        self.assertEqual((ntz["yd_high"], ntz["yd_low"]), (105.0, 95.0))
        complete = scanner.compute_ntz(daily, pd.DataFrame(), tuesday, after_close)
        self.assertEqual((complete["yd_high"], complete["yd_low"]), (120.0, 80.0))

    def test_html_has_no_whitespace_only_lines_without_failures(self):
        report = {
            "economic_events": [], "fed_speakers": [], "vix_regime": "moderate", "vix": 18.0,
            "spy_trend": "Range", "spy_sma_pos": "Above", "avg_conviction": 0,
            "scanned_count": 0, "passed_count": 0, "top_picks": [], "failures": [],
            "session_date": "Monday, November 09, 2026", "generated_at": "Friday 10:00 PM ET",
        }
        html = scanner.generate_html(report)
        self.assertTrue(all(line == line.rstrip() for line in html.splitlines()))
        self.assertIn("Avg Conv.", html)


if __name__ == "__main__":
    unittest.main()
