from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

from dsss.types.models import DriveFolder


@runtime_checkable
class DriveBackend(Protocol):
    """Backend interface for Drive operations."""

    def verify_root_folder(self, folder_id: str) -> None:
        """Validate that the given folder exists and is a folder."""

    def list_child_folders(self, parent_folder_id: str) -> Iterable[DriveFolder]:
        """Return direct child folders under the given parent folder."""

    def create_folder(self, parent_folder_id: str, folder_name: str) -> str:
        """Create a folder directly under the given parent and return its ID."""

    def upload_file(self, local_path: Path, parent_folder_id: str) -> str:
        """Upload a file to the given parent folder and return its Drive file ID."""
