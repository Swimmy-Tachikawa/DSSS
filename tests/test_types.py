import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dsss.types import (
    DriveFolder,
    LocalFile,
    LocalScanResult,
    UploadItemResult,
    UploadRunResult,
)


class TestTypes(unittest.TestCase):
    def test_dataclasses_are_frozen(self) -> None:
        jst = timezone(timedelta(hours=9))
        lf = LocalFile(
            path=Path("/tmp/a.txt"),
            name="a.txt",
            size_bytes=10,
            mtime_jst=datetime(2026, 1, 1, tzinfo=jst),
        )

        with self.assertRaises(FrozenInstanceError):
            lf.size_bytes = 20  # type: ignore[misc]

    def test_drive_folder_hashable(self) -> None:
        f1 = DriveFolder(folder_id="1", name="A")
        f2 = DriveFolder(folder_id="1", name="A")
        folders = {f1, f2}
        self.assertEqual(len(folders), 1)

    def test_local_scan_result_allows_empty(self) -> None:
        res = LocalScanResult(files=tuple())
        self.assertEqual(res.files, tuple())

    def test_upload_run_result_holds_tuple(self) -> None:
        jst = timezone(timedelta(hours=9))
        lf = LocalFile(
            path=Path("/tmp/a.txt"),
            name="a.txt",
            size_bytes=10,
            mtime_jst=datetime(2026, 1, 1, tzinfo=jst),
        )
        item = UploadItemResult(local_file=lf, ok=True, drive_file_id="D1")
        run = UploadRunResult(
            target_parent_folder_id="P1",
            created_date_folder_id="DF1",
            uploaded=(item,),
        )
        self.assertEqual(run.uploaded[0].drive_file_id, "D1")


if __name__ == "__main__":
    unittest.main()
