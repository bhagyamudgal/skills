import importlib.util
import pathlib
import unittest
from datetime import datetime, timedelta, timezone

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "skills" / "standup" / "scripts" / "gather.py"
SPEC = importlib.util.spec_from_file_location("gather", SCRIPT)
gather = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gather)

IST = timezone(timedelta(hours=5, minutes=30))


def local(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=IST)


class DefaultWindowTest(unittest.TestCase):
    def assert_window(self, now, expected_start, expected_end):
        start, end, _ = gather.default_window(now)
        self.assertEqual((start, end), (expected_start, expected_end))

    def test_weekday_afternoon_covers_previous_workday_up_to_todays_standup(self):
        self.assert_window(local(2026, 9, 10, 14, 48), local(2026, 9, 9, 10), local(2026, 9, 10, 10))

    def test_weekday_just_after_standup_hour_stops_at_todays_standup(self):
        self.assert_window(local(2026, 9, 30, 10, 26), local(2026, 9, 29, 10), local(2026, 9, 30, 10))

    def test_weekday_before_standup_hour_runs_from_previous_workday_to_now(self):
        self.assert_window(local(2026, 9, 11, 3, 18), local(2026, 9, 10, 10), local(2026, 9, 11, 3, 18))

    def test_monday_after_standup_hour_reaches_back_to_friday(self):
        self.assert_window(local(2026, 9, 28, 10, 18), local(2026, 9, 25, 10), local(2026, 9, 28, 10))

    def test_monday_before_standup_hour_reaches_back_to_friday(self):
        self.assert_window(local(2026, 9, 14, 1, 50), local(2026, 9, 11, 10), local(2026, 9, 14, 1, 50))

    def test_weekday_at_standup_hour_stops_at_todays_standup(self):
        self.assert_window(local(2026, 9, 16, 10), local(2026, 9, 15, 10), local(2026, 9, 16, 10))

    def test_weekday_one_minute_before_standup_hour_runs_to_now(self):
        self.assert_window(local(2026, 9, 16, 9, 59), local(2026, 9, 15, 10), local(2026, 9, 16, 9, 59))

    def test_weekend_run_covers_since_friday_standup_to_now(self):
        self.assert_window(local(2026, 9, 26, 15), local(2026, 9, 25, 10), local(2026, 9, 26, 15))

    def test_sunday_morning_run_covers_since_friday_standup_to_now(self):
        self.assert_window(local(2026, 9, 27, 9), local(2026, 9, 25, 10), local(2026, 9, 27, 9))

    def test_weekday_after_standup_hour_labels_the_window(self):
        _, _, label = gather.default_window(local(2026, 9, 16, 14))
        self.assertEqual(label, "previous workday, up to today's standup")


if __name__ == "__main__":
    unittest.main()
