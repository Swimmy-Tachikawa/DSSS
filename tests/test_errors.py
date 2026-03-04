import unittest
from pathlib import Path

from dsss.errors import (
    ConfigError,
    DriveAccessError,
    DuplicateDateFolderError,
    GDriveUploaderError,
    LocalScanError,
    UploadFailedError,
    ValidationError,
)


class TestErrors(unittest.TestCase):
    def test_inheritance_tree(self) -> None:
        self.assertTrue(issubclass(ConfigError, GDriveUploaderError))
        self.assertTrue(issubclass(ValidationError, GDriveUploaderError))
        self.assertTrue(issubclass(LocalScanError, GDriveUploaderError))
        self.assertTrue(issubclass(DriveAccessError, GDriveUploaderError))
        self.assertTrue(issubclass(DuplicateDateFolderError, DriveAccessError))

    def test_upload_failed_error_str(self) -> None:
        err1 = UploadFailedError(local_path=Path("/tmp/a.txt"), reason="network")
        self.assertIn("network", str(err1))
        self.assertIn("/tmp/a.txt", str(err1))

        err2 = UploadFailedError(
            local_path=Path("/tmp/a.txt"),
            reason="network",
            drive_parent_id="P999",
        )
        self.assertIn("P999", str(err2))


if __name__ == "__main__":
    unittest.main()
