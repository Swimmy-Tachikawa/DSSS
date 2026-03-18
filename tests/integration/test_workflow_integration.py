from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dsss.errors import DuplicateDateFolderError, ValidationError
from dsss.timeutils import JST, build_date_path, to_jst
from dsss.types import DriveFolder, UploadItemResult, UploadRunResult
from dsss.workflow import UploaderWorkflow


@dataclass(frozen=True, slots=True)
class _FolderNode:
    """In-memory folder node for fake Drive."""

    folder_id: str
    name: str
    parent_id: str | None


class FakeDriveAccessService:
    """Fake Drive service for integration testing."""

    def __init__(self) -> None:
        self._folders: dict[str, _FolderNode] = {}
        self._children: dict[str | None, list[str]] = {}
        self._upload_fail_names: set[str] = set()
        self._folder_seq = 0
        self.upload_log: list[tuple[str, str]] = []

    def add_folder(
        self,
        folder_id: str,
        name: str,
        parent_id: str | None,
    ) -> None:
        """Register a folder node."""
        self._folders[folder_id] = _FolderNode(
            folder_id=folder_id,
            name=name,
            parent_id=parent_id,
        )
        self._children.setdefault(parent_id, []).append(folder_id)
        self._children.setdefault(folder_id, [])

    def set_upload_fail_names(self, names: set[str]) -> None:
        """Configure file names that should fail on upload."""
        self._upload_fail_names = set(names)

    def verify_root_folder(self, root_folder_id: str) -> None:
        """Verify root folder existence."""
        if root_folder_id not in self._folders:
            raise ValidationError(f"Root folder not found: {root_folder_id}")

    def list_child_folders(self, root_folder_id: str) -> tuple[DriveFolder, ...]:
        """List direct child folders."""
        child_ids = self._children.get(root_folder_id, [])
        return tuple(
            DriveFolder(folder_id=folder_id, name=self._folders[folder_id].name)
            for folder_id in child_ids
        )

    def validate_child_folder(
        self,
        root_folder_id: str,
        child_folder_id: str,
    ) -> DriveFolder:
        """Validate that child_folder_id is a direct child of root."""
        node = self._folders.get(child_folder_id)
        if node is None or node.parent_id != root_folder_id:
            raise ValidationError(
                f"Folder is not a direct child of root: {child_folder_id}"
            )
        return DriveFolder(folder_id=node.folder_id, name=node.name)

    def get_or_create_date_folder(
        self,
        upload_parent_folder_id: str,
        target_date: datetime,
    ) -> tuple[str, str | None]:
        """Reuse or create date folder named YYYY/MM/DD."""
        folder_name = build_date_path(target_date)
        child_ids = self._children.get(upload_parent_folder_id, [])

        matched = [
            folder_id
            for folder_id in child_ids
            if self._folders[folder_id].name == folder_name
        ]

        if len(matched) >= 2:
            raise DuplicateDateFolderError(
                f"Duplicate date folder found: {folder_name}"
            )

        if len(matched) == 1:
            return matched[0], None

        self._folder_seq += 1
        new_id = f"date-{self._folder_seq}"
        self.add_folder(
            folder_id=new_id,
            name=folder_name,
            parent_id=upload_parent_folder_id,
        )
        return new_id, new_id

    def upload_files(
        self,
        local_files,
        parent_folder_id: str,
        created_date_folder_id: str | None,
    ) -> UploadRunResult:
        """Upload sequentially and continue even if some files fail."""
        uploaded_items: list[UploadItemResult] = []

        for index, local_file in enumerate(local_files, start=1):
            self.upload_log.append((parent_folder_id, local_file.name))

            if local_file.name in self._upload_fail_names:
                uploaded_items.append(
                    UploadItemResult(
                        local_file=local_file,
                        ok=False,
                        error_reason=f"Simulated upload failure: {local_file.name}",
                    )
                )
                continue

            uploaded_items.append(
                UploadItemResult(
                    local_file=local_file,
                    ok=True,
                    drive_file_id=f"file-{index}-{local_file.name}",
                )
            )

        return UploadRunResult(
            target_parent_folder_id=parent_folder_id,
            created_date_folder_id=created_date_folder_id,
            uploaded=tuple(uploaded_items),
        )


class WorkflowIntegrationTest(unittest.TestCase):
    """Integration tests across local_scan, workflow, and fake drive access."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.source_dir = Path(self.temp_dir.name)

        self.drive = FakeDriveAccessService()
        self.drive.add_folder("root", "root", None)
        self.drive.add_folder("class-a", "class-a", "root")
        self.drive.add_folder("other-parent", "other-parent", None)
        self.drive.add_folder("nested", "nested", "class-a")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_file(
        self,
        name: str,
        content: str,
        mtime_jst: datetime,
    ) -> Path:
        """Create a local file and set its mtime."""
        path = self.source_dir / name
        path.write_text(content, encoding="utf-8")

        mtime_utc = to_jst(mtime_jst).astimezone(timezone.utc).timestamp()
        os.utime(path, (mtime_utc, mtime_utc))
        return path

    def _make_workflow(self) -> UploaderWorkflow:
        """Create workflow bound to temp source dir."""
        return UploaderWorkflow(
            source_dir=self.source_dir,
            drive_root_folder_id="root",
            drive_access_service=self.drive,
        )

    def test_run_upload_reuses_existing_date_folder(self) -> None:
        """Existing date folder should be reused."""
        base = datetime(2026, 3, 18, 16, 10, tzinfo=JST)
        self._create_file("a.txt", "aaa", base)
        self._create_file("b.txt", "bbb", base + timedelta(minutes=10))

        existing_name = build_date_path(base + timedelta(minutes=10))
        self.drive.add_folder("existing-date", existing_name, "class-a")

        workflow = self._make_workflow()
        start = datetime(2026, 3, 18, 16, 0, tzinfo=JST)
        end = datetime(2026, 3, 18, 17, 10, tzinfo=JST)

        result = workflow.run_upload(
            upload_parent_folder_id="class-a",
            start=start,
            end=end,
        )

        self.assertEqual(result.target_parent_folder_id, "existing-date")
        self.assertIsNone(result.created_date_folder_id)
        self.assertEqual(len(result.uploaded), 2)
        self.assertTrue(all(item.ok for item in result.uploaded))
        self.assertEqual(
            [item.local_file.name for item in result.uploaded],
            ["a.txt", "b.txt"],
        )

    def test_run_upload_creates_new_date_folder(self) -> None:
        """Date folder should be created when absent."""
        target_time = datetime(2026, 3, 18, 18, 5, tzinfo=JST)
        self._create_file("report.txt", "data", target_time)

        workflow = self._make_workflow()
        start = datetime(2026, 3, 18, 18, 0, tzinfo=JST)
        end = datetime(2026, 3, 18, 19, 0, tzinfo=JST)

        result = workflow.run_upload(
            upload_parent_folder_id="class-a",
            start=start,
            end=end,
        )

        self.assertEqual(result.created_date_folder_id, "date-1")
        self.assertEqual(result.target_parent_folder_id, "date-1")
        self.assertEqual(self.drive._folders["date-1"].name, "2026/03/18")
        self.assertEqual(len(result.uploaded), 1)
        self.assertTrue(result.uploaded[0].ok)

    def test_partial_failure_continues_sequential_upload(self) -> None:
        """Upload should continue even if one file fails."""
        self._create_file("ok1.txt", "1", datetime(2026, 3, 18, 16, 0, tzinfo=JST))
        self._create_file("ng.txt", "2", datetime(2026, 3, 18, 16, 5, tzinfo=JST))
        self._create_file("ok2.txt", "3", datetime(2026, 3, 18, 16, 10, tzinfo=JST))

        self.drive.set_upload_fail_names({"ng.txt"})

        workflow = self._make_workflow()
        result = workflow.run_upload(
            upload_parent_folder_id="class-a",
            start=datetime(2026, 3, 18, 16, 0, tzinfo=JST),
            end=datetime(2026, 3, 18, 17, 0, tzinfo=JST),
        )

        self.assertEqual(len(result.uploaded), 3)
        self.assertEqual(
            [item.local_file.name for item in result.uploaded],
            ["ok1.txt", "ng.txt", "ok2.txt"],
        )
        self.assertEqual([item.ok for item in result.uploaded], [True, False, True])
        self.assertEqual(
            self.drive.upload_log,
            [
                (result.target_parent_folder_id, "ok1.txt"),
                (result.target_parent_folder_id, "ng.txt"),
                (result.target_parent_folder_id, "ok2.txt"),
            ],
        )
        self.assertIn("Simulated upload failure", result.uploaded[1].error_reason)

    def test_duplicate_date_folder_raises(self) -> None:
        """Duplicate date folder names should raise an error."""
        target_time = datetime(2026, 3, 18, 16, 30, tzinfo=JST)
        self._create_file("a.txt", "aaa", target_time)

        folder_name = build_date_path(target_time)
        self.drive.add_folder("dup-1", folder_name, "class-a")
        self.drive.add_folder("dup-2", folder_name, "class-a")

        workflow = self._make_workflow()

        with self.assertRaises(DuplicateDateFolderError):
            workflow.run_upload(
                upload_parent_folder_id="class-a",
                start=datetime(2026, 3, 18, 16, 0, tzinfo=JST),
                end=datetime(2026, 3, 18, 17, 0, tzinfo=JST),
            )

    def test_invalid_child_folder_raises(self) -> None:
        """Non-direct child folder should be rejected."""
        self._create_file(
            "sample.txt",
            "sample",
            datetime(2026, 3, 18, 16, 0, tzinfo=JST),
        )

        workflow = self._make_workflow()

        with self.assertRaises(ValidationError):
            workflow.run_upload(
                upload_parent_folder_id="nested",
                start=datetime(2026, 3, 18, 16, 0, tzinfo=JST),
                end=datetime(2026, 3, 18, 17, 0, tzinfo=JST),
            )

    def test_empty_scan_uses_start_as_target_date(self) -> None:
        """If scan result is empty, start should be used as target date."""
        workflow = self._make_workflow()
        start = datetime(2026, 3, 18, 16, 0, tzinfo=JST)
        end = datetime(2026, 3, 18, 17, 0, tzinfo=JST)

        result = workflow.run_upload(
            upload_parent_folder_id="class-a",
            start=start,
            end=end,
        )

        self.assertEqual(result.created_date_folder_id, "date-1")
        self.assertEqual(result.target_parent_folder_id, "date-1")
        self.assertEqual(self.drive._folders["date-1"].name, "2026/03/18")
        self.assertEqual(result.uploaded, ())

    def test_get_drive_folders_returns_direct_children(self) -> None:
        """get_drive_folders should return only direct children of root."""
        workflow = self._make_workflow()

        folders = workflow.get_drive_folders()

        self.assertEqual(
            {(folder.folder_id, folder.name) for folder in folders},
            {
                ("class-a", "class-a"),
            },
        )


if __name__ == "__main__":
    unittest.main()
