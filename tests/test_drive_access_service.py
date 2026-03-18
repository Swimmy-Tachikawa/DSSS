from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dsss.drive_access.service import DriveAccessService
from dsss.types.models import DriveFolder, LocalFile


JST = timezone(timedelta(hours=9))


class FakeDriveBackend:
    """Fake backend for DriveAccessService tests."""

    def __init__(self) -> None:
        self.verified_root_ids: list[str] = []
        self.child_folders_map: dict[str, tuple[DriveFolder, ...]] = {}
        self.created_folders: list[tuple[str, str]] = []
        self.uploaded_files: list[tuple[Path, str]] = []

        self.verify_root_error: Exception | None = None
        self.create_folder_result: str = "new-folder-id"
        self.create_folder_error: Exception | None = None

        self.upload_results: dict[tuple[Path, str], str] = {}
        self.upload_errors: dict[tuple[Path, str], Exception] = {}

    def verify_root_folder(self, folder_id: str) -> None:
        self.verified_root_ids.append(folder_id)
        if self.verify_root_error is not None:
            raise self.verify_root_error

    def list_child_folders(self, parent_folder_id: str) -> tuple[DriveFolder, ...]:
        return self.child_folders_map.get(parent_folder_id, ())

    def create_folder(self, parent_folder_id: str, folder_name: str) -> str:
        self.created_folders.append((parent_folder_id, folder_name))
        if self.create_folder_error is not None:
            raise self.create_folder_error
        return self.create_folder_result

    def upload_file(self, local_path: Path, parent_folder_id: str) -> str:
        key = (local_path, parent_folder_id)
        self.uploaded_files.append(key)

        if key in self.upload_errors:
            raise self.upload_errors[key]

        if key in self.upload_results:
            return self.upload_results[key]

        raise RuntimeError(f"Unexpected upload request: {key}")


class TestDriveAccessService(unittest.TestCase):
    """Unit tests for DriveAccessService."""

    def setUp(self) -> None:
        self.backend = FakeDriveBackend()
        self.service = DriveAccessService(self.backend)

        self.root_id = "root-001"
        self.child_a = DriveFolder(folder_id="child-a", name="A")
        self.child_b = DriveFolder(folder_id="child-b", name="B")

        self.backend.child_folders_map[self.root_id] = (
            self.child_a,
            self.child_b,
        )

    def _make_local_file(self, name: str) -> LocalFile:
        return LocalFile(
            path=Path(f"/tmp/{name}"),
            name=name,
            size_bytes=123,
            mtime_jst=datetime(2026, 3, 18, 16, 0, tzinfo=JST),
        )

    def test_verify_root_folder_calls_backend(self) -> None:
        self.service.verify_root_folder(self.root_id)
        self.assertEqual(self.backend.verified_root_ids, [self.root_id])

    def test_verify_root_folder_propagates_error(self) -> None:
        self.backend.verify_root_error = ValueError("invalid root")

        with self.assertRaisesRegex(ValueError, "invalid root"):
            self.service.verify_root_folder(self.root_id)

    def test_list_child_folders_returns_tuple(self) -> None:
        result = self.service.list_child_folders(self.root_id)

        self.assertEqual(result, (self.child_a, self.child_b))
        self.assertIsInstance(result, tuple)

    def test_validate_child_folder_returns_target(self) -> None:
        result = self.service.validate_child_folder(
            root_folder_id=self.root_id,
            child_folder_id="child-b",
        )

        self.assertEqual(result, self.child_b)

    def test_validate_child_folder_raises_when_not_direct_child(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Selected folder is not a direct child",
        ):
            self.service.validate_child_folder(
                root_folder_id=self.root_id,
                child_folder_id="child-x",
            )

    def test_find_date_folder_returns_existing_folder(self) -> None:
        target_date = datetime(2026, 2, 7, 10, 0, tzinfo=JST)
        date_folder = DriveFolder(folder_id="date-001", name="2026/02/07")

        self.backend.child_folders_map["upload-parent"] = (
            self.child_a,
            date_folder,
        )

        result = self.service.find_date_folder(
            upload_parent_folder_id="upload-parent",
            target_date=target_date,
        )

        self.assertEqual(result, date_folder)

    def test_find_date_folder_returns_none_when_not_found(self) -> None:
        target_date = datetime(2026, 2, 7, 10, 0, tzinfo=JST)
        self.backend.child_folders_map["upload-parent"] = (
            self.child_a,
            self.child_b,
        )

        result = self.service.find_date_folder(
            upload_parent_folder_id="upload-parent",
            target_date=target_date,
        )

        self.assertIsNone(result)

    def test_find_date_folder_raises_on_duplicate(self) -> None:
        target_date = datetime(2026, 2, 7, 10, 0, tzinfo=JST)

        self.backend.child_folders_map["upload-parent"] = (
            DriveFolder(folder_id="date-001", name="2026/02/07"),
            DriveFolder(folder_id="date-002", name="2026/02/07"),
        )

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate date folders found",
        ):
            self.service.find_date_folder(
                upload_parent_folder_id="upload-parent",
                target_date=target_date,
            )

    def test_create_date_folder_creates_formatted_folder_name(self) -> None:
        target_date = datetime(2026, 2, 7, 10, 0, tzinfo=JST)
        self.backend.create_folder_result = "created-777"

        result = self.service.create_date_folder(
            upload_parent_folder_id="upload-parent",
            target_date=target_date,
        )

        self.assertEqual(result, "created-777")
        self.assertEqual(
            self.backend.created_folders,
            [("upload-parent", "2026/02/07")],
        )

    def test_get_or_create_date_folder_returns_existing_without_creation(self) -> None:
        target_date = datetime(2026, 2, 7, 10, 0, tzinfo=JST)
        existing = DriveFolder(folder_id="date-existing", name="2026/02/07")
        self.backend.child_folders_map["upload-parent"] = (existing,)

        folder_id, created_id = self.service.get_or_create_date_folder(
            upload_parent_folder_id="upload-parent",
            target_date=target_date,
        )

        self.assertEqual(folder_id, "date-existing")
        self.assertIsNone(created_id)
        self.assertEqual(self.backend.created_folders, [])

    def test_get_or_create_date_folder_creates_when_missing(self) -> None:
        target_date = datetime(2026, 2, 7, 10, 0, tzinfo=JST)
        self.backend.child_folders_map["upload-parent"] = ()
        self.backend.create_folder_result = "created-999"

        folder_id, created_id = self.service.get_or_create_date_folder(
            upload_parent_folder_id="upload-parent",
            target_date=target_date,
        )

        self.assertEqual(folder_id, "created-999")
        self.assertEqual(created_id, "created-999")
        self.assertEqual(
            self.backend.created_folders,
            [("upload-parent", "2026/02/07")],
        )

    def test_upload_files_all_success(self) -> None:
        file_a = self._make_local_file("a.txt")
        file_b = self._make_local_file("b.txt")

        self.backend.upload_results[(file_a.path, "date-parent")] = "drive-a"
        self.backend.upload_results[(file_b.path, "date-parent")] = "drive-b"

        result = self.service.upload_files(
            local_files=(file_a, file_b),
            parent_folder_id="date-parent",
            created_date_folder_id="created-date-001",
        )

        self.assertEqual(result.target_parent_folder_id, "date-parent")
        self.assertEqual(result.created_date_folder_id, "created-date-001")
        self.assertEqual(len(result.uploaded), 2)

        self.assertTrue(result.uploaded[0].ok)
        self.assertEqual(result.uploaded[0].local_file, file_a)
        self.assertEqual(result.uploaded[0].drive_file_id, "drive-a")
        self.assertIsNone(result.uploaded[0].error_reason)

        self.assertTrue(result.uploaded[1].ok)
        self.assertEqual(result.uploaded[1].local_file, file_b)
        self.assertEqual(result.uploaded[1].drive_file_id, "drive-b")
        self.assertIsNone(result.uploaded[1].error_reason)

    def test_upload_files_continues_after_failure(self) -> None:
        file_a = self._make_local_file("a.txt")
        file_b = self._make_local_file("b.txt")
        file_c = self._make_local_file("c.txt")

        self.backend.upload_results[(file_a.path, "date-parent")] = "drive-a"
        self.backend.upload_errors[(file_b.path, "date-parent")] = RuntimeError(
            "upload failed"
        )
        self.backend.upload_results[(file_c.path, "date-parent")] = "drive-c"

        result = self.service.upload_files(
            local_files=(file_a, file_b, file_c),
            parent_folder_id="date-parent",
            created_date_folder_id=None,
        )

        self.assertEqual(len(result.uploaded), 3)

        self.assertTrue(result.uploaded[0].ok)
        self.assertEqual(result.uploaded[0].drive_file_id, "drive-a")

        self.assertFalse(result.uploaded[1].ok)
        self.assertIsNone(result.uploaded[1].drive_file_id)
        self.assertEqual(result.uploaded[1].error_reason, "upload failed")

        self.assertTrue(result.uploaded[2].ok)
        self.assertEqual(result.uploaded[2].drive_file_id, "drive-c")

        self.assertEqual(
            self.backend.uploaded_files,
            [
                (file_a.path, "date-parent"),
                (file_b.path, "date-parent"),
                (file_c.path, "date-parent"),
            ],
        )

    def test_upload_files_empty_input_returns_empty_result(self) -> None:
        result = self.service.upload_files(
            local_files=(),
            parent_folder_id="date-parent",
            created_date_folder_id=None,
        )

        self.assertEqual(result.target_parent_folder_id, "date-parent")
        self.assertIsNone(result.created_date_folder_id)
        self.assertEqual(result.uploaded, ())
        self.assertEqual(self.backend.uploaded_files, [])


if __name__ == "__main__":
    unittest.main()
