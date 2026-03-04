# tests/test_local_scan_debug.py
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dsss.local_scan import scan_local_files
from dsss.timeutils import JST, is_within_range


class TestLocalScanDebug(unittest.TestCase):
    def test_mtime_interpretation_debug(self) -> None:
        """
        Debug test to confirm how mtime is interpreted and converted to JST.

        This test does NOT use start/end filtering to isolate issues to:
        - os.utime timestamp handling
        - stat.st_mtime interpretation
        - conversion to timezone-aware JST datetime
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            f1 = base / "a.txt"
            f1.write_text("a", encoding="utf-8")

            # Set explicit UTC times
            t1_utc = datetime(2026, 3, 4, 0, 0, 0, tzinfo=timezone.utc)
            os.utime(f1, (t1_utc.timestamp(), t1_utc.timestamp()))

            result = scan_local_files(base)
            names = [f.name for f in result.files]

            self.assertIn(
                "a.txt",
                names,
                msg=(
                    "a.txt was not found by scan_local_files without filtering. "
                    f"Found names={names!r}"
                ),
            )

            lf = next(f for f in result.files if f.name == "a.txt")

            expected_jst = t1_utc.astimezone(JST)
            actual_jst = lf.mtime_jst

            # Compare as ISO strings to make timezone differences explicit in failure messages.
            self.assertEqual(
                expected_jst.isoformat(),
                actual_jst.isoformat(),
                msg=(
                    "mtime conversion mismatch.\n"
                    f"stat.st_mtime={f1.stat().st_mtime}\n"
                    f"t1_utc={t1_utc.isoformat()}\n"
                    f"expected_jst={expected_jst.isoformat()}\n"
                    f"actual_mtime_jst={actual_jst.isoformat()}\n"
                    "If actual_mtime_jst is off by 9 hours, the mtime may be treated as "
                    "naive local time but converted as UTC (or vice versa)."
                ),
            )

    def test_range_filter_debug(self) -> None:
        """
        Debug test to expose why range filtering might exclude all files.

        If filtering results in 0 files, the assertion message will include:
        - start/end
        - each file's computed mtime_jst
        - is_within_range verdict
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            f1 = base / "a.txt"
            f2 = base / "b.txt"
            f1.write_text("a", encoding="utf-8")
            f2.write_text("bb", encoding="utf-8")

            # Fixed UTC times for deterministic behavior
            t1_utc = datetime(2026, 3, 4, 0, 0, 0, tzinfo=timezone.utc)
            t2_utc = datetime(2026, 3, 4, 1, 0, 0, tzinfo=timezone.utc)
            os.utime(f1, (t1_utc.timestamp(), t1_utc.timestamp()))
            os.utime(f2, (t2_utc.timestamp(), t2_utc.timestamp()))

            # Define a range that should include both files, in JST
            start = (t1_utc - timedelta(minutes=10)).astimezone(JST)
            end = (t2_utc + timedelta(minutes=10)).astimezone(JST)

            # First scan without filtering to get computed mtimes
            unfiltered = scan_local_files(base)
            debug_lines = [
                f"start={start.isoformat()}",
                f"end={end.isoformat()}",
                "unfiltered_files:",
            ]
            for lf in unfiltered.files:
                verdict = is_within_range(lf.mtime_jst, start, end)
                debug_lines.append(
                    f"  name={lf.name} mtime_jst={lf.mtime_jst.isoformat()} "
                    f"in_range={verdict}"
                )

            # Now scan with filtering
            filtered = scan_local_files(base, start=start, end=end)
            filtered_names = [f.name for f in filtered.files]

            self.assertGreater(
                len(filtered.files),
                0,
                msg=(
                    "Range filtering returned 0 files unexpectedly.\n"
                    + "\n".join(debug_lines)
                    + f"\nfiltered_names={filtered_names!r}\n"
                    "This indicates a mismatch between computed mtime_jst and the "
                    "start/end range (timezone interpretation issue likely)."
                ),
            )


if __name__ == "__main__":
    unittest.main()
