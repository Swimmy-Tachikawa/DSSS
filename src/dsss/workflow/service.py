from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from dsss.errors import ConfigError, ValidationError
from dsss.local_scan import scan_local_files
from dsss.timeutils import to_jst
from dsss.types import DriveFolder, LocalScanResult, UploadRunResult


class UploaderWorkflow:
    """
    Main orchestration layer for DSSS upload flow.

    This class combines local scanning and Drive access operations while
    keeping UI responsibilities outside of the library.
    """

    def __init__(
        self,
        source_dir: Path | str,
        drive_root_folder_id: str,
        drive_access_service: object,
    ) -> None:
        """
        Initialize workflow with fixed local source directory and Drive root.

        Validation policy:
        - source_dir must exist and be a directory
        - drive_root_folder_id must be non-empty
        - drive_root_folder_id is verified immediately via drive_access_service
        """
        src = Path(source_dir).expanduser().resolve()
        if not src.exists() or not src.is_dir():
            raise ConfigError(f"source_dir is not a directory: {src}")

        if not isinstance(drive_root_folder_id, str) or not drive_root_folder_id.strip():
            raise ConfigError("drive_root_folder_id must be a non-empty string.")

        self._source_dir = src
        self._drive_root_folder_id = drive_root_folder_id
        self._drive_access_service = drive_access_service

        self._verify_drive_root()

    @property
    def source_dir(self) -> Path:
        """Return the resolved source directory."""
        return self._source_dir

    @property
    def drive_root_folder_id(self) -> str:
        """Return the fixed Drive root folder id."""
        return self._drive_root_folder_id

    def _verify_drive_root(self) -> None:
        """Verify that the configured Drive root folder is valid."""
        self._drive_access_service.verify_root_folder(self._drive_root_folder_id)

    def scan(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> LocalScanResult:
        """
        Scan local files under source_dir.

        If both start and end are provided, filtering is performed under
        the local_scan rules: direct children only, no recursion, mtime in JST,
        and range [start, end).
        """
        return scan_local_files(
            source_dir=self._source_dir,
            start=start,
            end=end,
        )

    def get_drive_folders(self) -> tuple[DriveFolder, ...]:
        """
        Return direct child folders under the configured Drive root folder.

        UI-side selection is intentionally outside this library.
        """
        folders = self._drive_access_service.list_child_folders(
            self._drive_root_folder_id
        )
        return tuple(folders)

    def prepare_date_folder(
        self,
        upload_parent_folder_id: str,
        target_date: datetime,
    ) -> tuple[str, Optional[str]]:
        """
        Validate selected upload parent folder and prepare a date folder.

        Returns:
            (date_folder_id, created_date_folder_id)

        created_date_folder_id is:
        - None if an existing date folder was reused
        - the new folder id if the date folder was newly created
        """
        if not isinstance(upload_parent_folder_id, str) or not upload_parent_folder_id.strip():
            raise ValidationError(
                "upload_parent_folder_id must be a non-empty string."
            )

        target_date_jst = to_jst(target_date)

        self._drive_access_service.validate_child_folder(
            root_folder_id=self._drive_root_folder_id,
            child_folder_id=upload_parent_folder_id,
        )

        return self._drive_access_service.get_or_create_date_folder(
            upload_parent_folder_id=upload_parent_folder_id,
            target_date=target_date_jst,
        )

    def run_upload(
        self,
        upload_parent_folder_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        target_date: Optional[datetime] = None,
    ) -> UploadRunResult:
        """
        Execute the full upload flow.

        Flow:
        1. scan local files
        2. validate selected upload parent folder
        3. get or create date folder
        4. upload files sequentially
        5. return aggregated UploadRunResult

        target_date:
        - if provided, it is used for date-folder naming
        - otherwise the latest mtime_jst in the scanned files is used
        - if no files are found, start must be provided and target_date falls
          back to start
        """
        scan_result = self.scan(start=start, end=end)

        if target_date is None:
            target_date = self._resolve_target_date(
                scan_result=scan_result,
                start=start,
            )

        date_folder_id, created_date_folder_id = self.prepare_date_folder(
            upload_parent_folder_id=upload_parent_folder_id,
            target_date=target_date,
        )

        return self._drive_access_service.upload_files(
            local_files=scan_result.files,
            parent_folder_id=date_folder_id,
            created_date_folder_id=created_date_folder_id,
        )

    @staticmethod
    def _resolve_target_date(
        scan_result: LocalScanResult,
        start: Optional[datetime],
    ) -> datetime:
        """
        Resolve date-folder target date.

        Priority:
        1. latest scanned file mtime_jst
        2. start datetime (converted by caller path later)
        3. error if neither is available
        """
        if scan_result.files:
            return max(file.mtime_jst for file in scan_result.files)

        if start is not None:
            return start

        raise ValidationError(
            "target_date could not be resolved because scan result is empty "
            "and start was not provided."
        )
