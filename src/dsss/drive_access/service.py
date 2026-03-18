from __future__ import annotations

from datetime import datetime
from typing import Iterable

from dsss.drive_access.backend import DriveBackend
from dsss.types.models import (
    DriveFolder,
    LocalFile,
    UploadItemResult,
    UploadRunResult,
)


class DriveAccessService:
    """Service layer for Drive-related operations."""

    def __init__(self, backend: DriveBackend) -> None:
        self._backend = backend

    def verify_root_folder(self, folder_id: str) -> None:
        """Validate that the root folder exists and is usable."""
        self._backend.verify_root_folder(folder_id)

    def list_child_folders(self, root_folder_id: str) -> tuple[DriveFolder, ...]:
        """Return direct child folders under the root folder."""
        return tuple(self._backend.list_child_folders(root_folder_id))

    def validate_child_folder(
        self,
        root_folder_id: str,
        child_folder_id: str,
    ) -> DriveFolder:
        """Validate that the folder is a direct child of the root folder."""
        for folder in self._backend.list_child_folders(root_folder_id):
            if folder.folder_id == child_folder_id:
                return folder

        raise ValueError(
            "Selected folder is not a direct child of the configured root folder."
        )

    def find_date_folder(
        self,
        upload_parent_folder_id: str,
        target_date: datetime,
    ) -> DriveFolder | None:
        """Find a date folder directly under the parent folder."""
        folder_name = target_date.strftime("%Y/%m/%d")
        matches = [
            folder
            for folder in self._backend.list_child_folders(upload_parent_folder_id)
            if folder.name == folder_name
        ]

        if len(matches) > 1:
            raise ValueError(
                f"Duplicate date folders found for '{folder_name}'."
            )

        if len(matches) == 1:
            return matches[0]

        return None

    def create_date_folder(
        self,
        upload_parent_folder_id: str,
        target_date: datetime,
    ) -> str:
        """Create a date folder directly under the parent folder."""
        folder_name = target_date.strftime("%Y/%m/%d")
        return self._backend.create_folder(upload_parent_folder_id, folder_name)

    def get_or_create_date_folder(
        self,
        upload_parent_folder_id: str,
        target_date: datetime,
    ) -> tuple[str, str | None]:
        """Return date folder ID and created folder ID if newly created.

        Returns:
            tuple[str, str | None]:
                - target folder ID actually used
                - created folder ID if a new folder was created, otherwise None
        """
        existing = self.find_date_folder(upload_parent_folder_id, target_date)
        if existing is not None:
            return existing.folder_id, None

        created_folder_id = self.create_date_folder(
            upload_parent_folder_id,
            target_date,
        )
        return created_folder_id, created_folder_id

    def upload_files(
        self,
        local_files: Iterable[LocalFile],
        parent_folder_id: str,
        created_date_folder_id: str | None = None,
    ) -> UploadRunResult:
        """Upload files sequentially.

        This method continues even if one file upload fails.
        """
        uploaded_items: list[UploadItemResult] = []

        for local_file in local_files:
            try:
                drive_file_id = self._backend.upload_file(
                    local_path=local_file.path,
                    parent_folder_id=parent_folder_id,
                )
                item = UploadItemResult(
                    local_file=local_file,
                    ok=True,
                    drive_file_id=drive_file_id,
                    error_reason=None,
                )
            except Exception as exc:  # noqa: BLE001
                item = UploadItemResult(
                    local_file=local_file,
                    ok=False,
                    drive_file_id=None,
                    error_reason=str(exc),
                )

            uploaded_items.append(item)

        return UploadRunResult(
            target_parent_folder_id=parent_folder_id,
            created_date_folder_id=created_date_folder_id,
            uploaded=tuple(uploaded_items),
        )
