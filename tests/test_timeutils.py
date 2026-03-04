import unittest
from datetime import datetime, timedelta, timezone

from dsss.timeutils import JST, build_date_path, is_within_range, to_jst


class TestTimeUtils(unittest.TestCase):
    def test_to_jst_from_utc(self) -> None:
        dt_utc = datetime(2026, 3, 4, 0, 0, 0, tzinfo=timezone.utc)
        dt_jst = to_jst(dt_utc)
        self.assertEqual(dt_jst.tzinfo, JST)
        self.assertEqual(dt_jst.hour, 9)

    def test_to_jst_from_naive_treat_as_utc(self) -> None:
        dt_naive = datetime(2026, 3, 4, 0, 0, 0)
        dt_jst = to_jst(dt_naive)
        self.assertEqual(dt_jst.tzinfo, JST)
        self.assertEqual(dt_jst.hour, 9)

    def test_is_within_range_boundaries(self) -> None:
        base = datetime(2026, 3, 4, 0, 0, 0, tzinfo=timezone.utc)
        start = base
        end = base + timedelta(seconds=10)

        self.assertTrue(is_within_range(base, start, end))
        self.assertTrue(is_within_range(base + timedelta(seconds=9), start, end))
        self.assertFalse(is_within_range(base + timedelta(seconds=10), start, end))

    def test_build_date_path(self) -> None:
        dt_utc = datetime(2026, 3, 4, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(build_date_path(dt_utc), "2026/03/04")


if __name__ == "__main__":
    unittest.main()
