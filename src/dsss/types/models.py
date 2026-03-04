from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True, slots=True)
class LocalFile:
    """
    A file found by local scanning.

    mtime_jst is expected to be a timezone-aware datetime in JST.
    Conversion will be handled in a later phase (timeutils).
    """

    path: Path
    name: str
    size_bytes: int
    mtime_jst: datetime


@dataclass(frozen=True, slots=True)
class DriveFolder:
    """A Google Drive folder representation."""

    folder_id: str
    name: str


@dataclass(frozen=True, slots=True)
class LocalScanResult:
    """
    Local scan result.

    files can be empty; callers may decide to re-scan or exit.
    """

    files: Tuple[LocalFile, ...]


@dataclass(frozen=True, slots=True)
class UploadItemResult:
    """
    Upload result for a single file.

    If ok is True, drive_file_id should be present.
    If ok is False, error_reason should be present.
    """

    local_file: LocalFile
    ok: bool
    drive_file_id: Optional[str] = None
    error_reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class UploadRunResult:
    """Aggregated result for a single upload run."""

    target_parent_folder_id: str
    created_date_folder_id: Optional[str]
    uploaded: Tuple[UploadItemResult, ...]
