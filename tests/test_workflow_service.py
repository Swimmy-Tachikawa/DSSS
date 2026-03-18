from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dsss.errors import ConfigError, ValidationError
from dsss.timeutils import JST, to_jst
from dsss.types import (
    DriveFolder,
    LocalFile,
    LocalScanResult,
    UploadItemResult,
    UploadRunResult,
)
from dsss.workflow import UploaderWorkflow


class FakeDriveAccessService:
    """Fake drive access service for workflow unit tests."""

    def __init__(self) -> None:
        self.verify_root_folder_calls: list[str] = []
        self.list_child_folders_calls: list[str] = []
        self.validate_child_folder_calls: list[tuple[str, str]] = []
        self.get_or_create_date_folder_calls: list[tuple[str, datetime]] = []
        self.upload_files_calls: list[tuple[tuple[LocalFile, ...], str, str | None]] = []

        self.child_folders: tuple[DriveFolder, ...] = ()
        self.date_folder_result: tuple[str, str | None] = ("date-folder-id", None)
        self.upload_result: UploadRunResult | None = None

    def verify_root_folder(self, root_folder_id: str) -> None:
        self.verify_root_folder_calls.append(root_folder_id)

    def list_child_folders(self, root_folder_id: str) -> tuple[DriveFolder, ...]:
        self.list_child_folders_calls.append(root_folder_id)
        return self.child_folders

    def validate_child_folder(
        self,
        root_folder_id: str,
        child_folder_id: str,
    ) -> None:
        self.validate_child_folder_calls.append((root_folder_id, child_folder_id))

    def get_or_create_date_folder(
        self,
        upload_parent_folder_id: str,
        target_date: datetime,
    ) -> tuple[str, str | None]:
        self.get_or_create_date_folder_calls.append(
            (upload_parent_folder_id, target_date)
        )
        return self.date_folder_result

    def upload_files(
        self,
        local_files: tuple[LocalFile, ...],
        parent_folder_id: str,
        created_date_folder_id: str | None,
    ) -> UploadRunResult:
        self.upload_files_calls.append(
            (tuple(local_files), parent_folder_id, created_date_folder_id)
        )
        if self.upload_result is None:
            return UploadRunResult(
                target_parent_folder_id=parent_folder_id,
                created_date_folder_id=created_date_folder_id,
                uploaded=(),
            )
        return self.upload_result


class TestUploaderWorkflow(unittest.TestCase):
    """Unit tests for UploaderWorkflow."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.source_dir = Path(self.temp_dir.name)
        self.drive_service = FakeDriveAccessService()
        self.root_folder_id = "root-123"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_workflow(self) -> UploaderWorkflow:
        return UploaderWorkflow(
            source_dir=self.source_dir,
            drive_root_folder_id=self.root_folder_id,
            drive_access_service=self.drive_service,
        )

    def _make_local_file(
        self,
        name: str,
        dt: datetime,
        size_bytes: int = 100,
    ) -> LocalFile:
        return LocalFile(
            path=self.source_dir / name,
            name=name,
            size_bytes=size_bytes,
            mtime_jst=to_jst(dt),
        )

    def test_init_verifies_root_folder(self) -> None:
        workflow = self._create_workflow()

        self.assertEqual(workflow.source_dir, self.source_dir.resolve())
        self.assertEqual(workflow.drive_root_folder_id, self.root_folder_id)
        self.assertEqual(
            self.drive_service.verify_root_folder_calls,
            [self.root_folder_id],
        )
        self.assertIsInstance(workflow, UploaderWorkflow)

    def test_init_raises_when_source_dir_is_invalid(self) -> None:
        missing_dir = self.source_dir / "missing"

        with self.assertRaises(ConfigError):
            UploaderWorkflow(
                source_dir=missing_dir,
                drive_root_folder_id=self.root_folder_id,
                drive_access_service=self.drive_service,
            )

    def test_init_raises_when_root_folder_id_is_empty(self) -> None:
        with self.assertRaises(ConfigError):
            UploaderWorkflow(
                source_dir=self.source_dir,
                drive_root_folder_id="",
                drive_access_service=self.drive_service,
            )

    @patch("dsss.workflow.service.scan_local_files")
    def test_scan_delegates_to_local_scan(self, mock_scan_local_files) -> None:
        expected = LocalScanResult(files=())
        mock_scan_local_files.return_value = expected

        workflow = self._create_workflow()
        start = datetime(2026, 3, 18, 16, 0, tzinfo=JST)
        end = datetime(2026, 3, 18, 17, 10, tzinfo=JST)

        result = workflow.scan(start=start, end=end)

        self.assertIs(result, expected)
        mock_scan_local_files.assert_called_once_with(
            source_dir=self.source_dir.resolve(),
            start=start,
            end=end,
        )

    def test_get_drive_folders_returns_child_folders(self) -> None:
        self.drive_service.child_folders = (
            DriveFolder(folder_id="a", name="A"),
            DriveFolder(folder_id="b", name="B"),
        )
        workflow = self._create_workflow()

        result = workflow.get_drive_folders()

        self.assertEqual(result, self.drive_service.child_folders)
        self.assertEqual(
            self.drive_service.list_child_folders_calls,
            [self.root_folder_id],
        )

    def test_prepare_date_folder_validates_and_returns_existing_folder(self) -> None:
        self.drive_service.date_folder_result = ("date-folder-id", None)
        workflow = self._create_workflow()
        target_date = datetime(2026, 3, 18, 16, 30, tzinfo=timezone.utc)

        folder_id, created_id = workflow.prepare_date_folder(
            upload_parent_folder_id="parent-1",
            target_date=target_date,
        )

        self.assertEqual(folder_id, "date-folder-id")
        self.assertIsNone(created_id)
        self.assertEqual(
            self.drive_service.validate_child_folder_calls,
            [(self.root_folder_id, "parent-1")],
        )
        self.assertEqual(
            self.drive_service.get_or_create_date_folder_calls,
            [("parent-1", to_jst(target_date))],
        )

    def test_prepare_date_folder_returns_created_folder(self) -> None:
        self.drive_service.date_folder_result = (
            "date-folder-id",
            "created-folder-id",
        )
        workflow = self._create_workflow()
        target_date = datetime(2026, 3, 18, 9, 0, tzinfo=timezone.utc)

        folder_id, created_id = workflow.prepare_date_folder(
            upload_parent_folder_id="parent-1",
            target_date=target_date,
        )

        self.assertEqual(folder_id, "date-folder-id")
        self.assertEqual(created_id, "created-folder-id")

    def test_prepare_date_folder_raises_for_empty_parent_id(self) -> None:
        workflow = self._create_workflow()

        with self.assertRaises(ValidationError):
            workflow.prepare_date_folder(
                upload_parent_folder_id="",
                target_date=datetime(2026, 3, 18, 16, 0, tzinfo=JST),
            )

    @patch("dsss.workflow.service.scan_local_files")
    def test_run_upload_uses_latest_mtime_when_target_date_is_not_given(
        self,
        mock_scan_local_files,
    ) -> None:
        file1 = self._make_local_file(
            "a.txt",
            datetime(2026, 3, 18, 16, 10, tzinfo=JST),
        )
        file2 = self._make_local_file(
            "b.txt",
            datetime(2026, 3, 18, 16, 50, tzinfo=JST),
        )
        scan_result = LocalScanResult(files=(file1, file2))
        mock_scan_local_files.return_value = scan_result

        upload_result = UploadRunResult(
            target_parent_folder_id="date-folder-id",
            created_date_folder_id="created-folder-id",
            uploaded=(
                UploadItemResult(
                    local_file=file1,
                    ok=True,
                    drive_file_id="drive-a",
                ),
                UploadItemResult(
                    local_file=file2,
                    ok=True,
                    drive_file_id="drive-b",
                ),
            ),
        )
        self.drive_service.date_folder_result = (
            "date-folder-id",
            "created-folder-id",
        )
        self.drive_service.upload_result = upload_result

        workflow = self._create_workflow()
        result = workflow.run_upload(
            upload_parent_folder_id="parent-1",
            start=datetime(2026, 3, 18, 16, 0, tzinfo=JST),
            end=datetime(2026, 3, 18, 17, 10, tzinfo=JST),
        )

        self.assertEqual(result, upload_result)
        self.assertEqual(
            self.drive_service.validate_child_folder_calls,
            [(self.root_folder_id, "parent-1")],
        )
        self.assertEqual(
            self.drive_service.get_or_create_date_folder_calls,
            [("parent-1", file2.mtime_jst)],
        )
        self.assertEqual(len(self.drive_service.upload_files_calls), 1)

        uploaded_files, parent_folder_id, created_date_folder_id = (
            self.drive_service.upload_files_calls[0]
        )
        self.assertEqual(uploaded_files, (file1, file2))
        self.assertEqual(parent_folder_id, "date-folder-id")
        self.assertEqual(created_date_folder_id, "created-folder-id")

    @patch("dsss.workflow.service.scan_local_files")
    def test_run_upload_uses_explicit_target_date(self, mock_scan_local_files) -> None:
        file1 = self._make_local_file(
            "a.txt",
            datetime(2026, 3, 18, 16, 10, tzinfo=JST),
        )
        scan_result = LocalScanResult(files=(file1,))
        mock_scan_local_files.return_value = scan_result

        explicit_target_date = datetime(2026, 3, 17, 23, 0, tzinfo=timezone.utc)

        workflow = self._create_workflow()
        workflow.run_upload(
            upload_parent_folder_id="parent-1",
            start=datetime(2026, 3, 18, 16, 0, tzinfo=JST),
            end=datetime(2026, 3, 18, 17, 10, tzinfo=JST),
            target_date=explicit_target_date,
        )

        self.assertEqual(
            self.drive_service.get_or_create_date_folder_calls,
            [("parent-1", to_jst(explicit_target_date))],
        )

    @patch("dsss.workflow.service.scan_local_files")
    def test_run_upload_empty_scan_uses_start_as_target_date(
        self,
        mock_scan_local_files,
    ) -> None:
        mock_scan_local_files.return_value = LocalScanResult(files=())
        workflow = self._create_workflow()

        start = datetime(2026, 3, 18, 16, 0, tzinfo=JST)
        end = datetime(2026, 3, 18, 17, 10, tzinfo=JST)

        workflow.run_upload(
            upload_parent_folder_id="parent-1",
            start=start,
            end=end,
        )

        self.assertEqual(
            self.drive_service.get_or_create_date_folder_calls,
            [("parent-1", to_jst(start))],
        )
        self.assertEqual(len(self.drive_service.upload_files_calls), 1)

        uploaded_files, _, _ = self.drive_service.upload_files_calls[0]
        self.assertEqual(uploaded_files, ())

    @patch("dsss.workflow.service.scan_local_files")
    def test_run_upload_empty_scan_without_start_raises_validation_error(
        self,
        mock_scan_local_files,
    ) -> None:
        mock_scan_local_files.return_value = LocalScanResult(files=())
        workflow = self._create_workflow()

        with self.assertRaises(ValidationError):
            workflow.run_upload(
                upload_parent_folder_id="parent-1",
                start=None,
                end=None,
            )


if __name__ == "__main__":
    unittest.main()
