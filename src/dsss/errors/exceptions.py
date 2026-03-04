from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class GDriveUploaderError(Exception):
    """Base exception for this library."""


class ConfigError(GDriveUploaderError):
    """Raised when configuration/initialization is invalid."""


class ValidationError(GDriveUploaderError):
    """Raised when input/state validation fails."""


class LocalScanError(GDriveUploaderError):
    """Raised when local file scanning fails due to I/O or permissions."""


class DriveAccessError(GDriveUploaderError):
    """Raised when Google Drive access or API operations fail."""


class DuplicateDateFolderError(DriveAccessError):
    """Raised when multiple date folders with the same name are found."""


@dataclass(frozen=True, slots=True)
class UploadFailedError(DriveAccessError):
    """
    Represents a single file upload failure.

    This is modeled as a dataclass so it can be kept as structured data
    while continuing the sequential upload process.
    """

    local_path: Path
    reason: str
    drive_parent_id: Optional[str] = None

    def __str__(self) -> str:
        base = (
            f"Upload failed: path={str(self.local_path)!r} "
            f"reason={self.reason!r}"
        )
        if self.drive_parent_id is not None:
            base += f" parent_id={self.drive_parent_id!r}"
        return base
