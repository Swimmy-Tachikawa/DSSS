import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dsss.errors import LocalScanError
from dsss.local_scan import scan_local_files
from dsss.timeutils import JST


class TestLocalScan(unittest.TestCase):
    def test_scan_direct_children_only_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            f1 = base / "a.txt"
            f2 = base / "b.txt"
            d1 = base / "dir1"
            d1.mkdir()
            nested = d1 / "nested.txt"
            nested.write_text("nested", encoding="utf-8")

            f1.write_text("a", encoding="utf-8")
            f2.write_text("bb", encoding="utf-8")

            # Set mtimes explicitly
            now = datetime.now(tz=timezone.utc)
            t1 = now - timedelta(hours=2)
            t2 = now - timedelta(hours=1)

            os.utime(f1, (t1.timestamp(), t1.timestamp()))
            os.utime(f2, (t2.timestamp(), t2.timestamp()))

            # Create a symlink if possible
            symlink_path = base / "link.txt"
            try:
                symlink_path.symlink_to(f1)
            except (OSError, NotImplementedError):
                symlink_path = None

            start = (now - timedelta(hours=3)).astimezone(JST)
            end = (now - timedelta(minutes=30)).astimezone(JST)

            result = scan_local_files(base, start=start, end=end)

            names = [f.name for f in result.files]
            self.assertIn("a.txt", names)
            self.assertIn("b.txt", names)
            self.assertNotIn("nested.txt", names)  # Not direct child

            if symlink_path is not None:
                self.assertNotIn("link.txt", names)  # Excluded symlink

    def test_scan_requires_both_start_and_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "a.txt").write_text("a", encoding="utf-8")

            start = datetime.now(tz=timezone.utc).astimezone(JST)
            with self.assertRaises(LocalScanError):
                scan_local_files(base, start=start, end=None)

    def test_invalid_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "not_exist"
            with self.assertRaises(LocalScanError):
                scan_local_files(base)

    def test_empty_result_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            result = scan_local_files(base)
            self.assertEqual(result.files, tuple())


if __name__ == "__main__":
    unittest.main()
