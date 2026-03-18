from __future__ import annotations

from pathlib import Path

from gdrivemgr import AuthInfo, GoogleDriveManager

from dsss.types.models import DriveFolder


FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class GDriveMgrBackend:
    """gdrivemgr-based backend implementation."""

    def __init__(self, auth_info: AuthInfo) -> None:
        self._manager = GoogleDriveManager(auth_info)

    def verify_root_folder(self, folder_id: str) -> None:
        """Validate that the given folder can be opened as a Drive root."""
        local = self._manager.open(folder_id)

        root_info = local.get_item(folder_id)
        if root_info is None:
            raise ValueError("Root folder was not found.")

        if root_info.mime_type != FOLDER_MIME_TYPE:
            raise ValueError("Configured root ID is not a folder.")

    def list_child_folders(self, parent_folder_id: str) -> tuple[DriveFolder, ...]:
        """Return direct child folders under the given parent."""
        local = self._manager.open(parent_folder_id)

        folders: list[DriveFolder] = []
        for item in local.list_children(parent_folder_id):
            if item.mime_type != FOLDER_MIME_TYPE:
                continue

            folders.append(
                DriveFolder(
                    folder_id=item.item_id,
                    name=item.name,
                )
            )

        return tuple(folders)

    def create_folder(self, parent_folder_id: str, folder_name: str) -> str:
        """Create a folder under the given parent and return its ID."""
        local = self._manager.open(parent_folder_id)
        local_id = local.create_folder(folder_name, parent_folder_id)

        plan = self._manager.build_plan()
        result = self._manager.apply_plan(plan)

        created = result.local_to_remote_id_map.get(local_id)
        if created is None:
            raise RuntimeError(
                "Folder creation completed but no folder ID was returned."
            )

        return created

    def upload_file(self, local_path: Path, parent_folder_id: str) -> str:
        """Upload a file and return its Drive file ID."""
        local = self._manager.open(parent_folder_id)
        local_id = local.upload_file(str(local_path), parent_folder_id)

        plan = self._manager.build_plan()
        result = self._manager.apply_plan(plan)

        created = result.local_to_remote_id_map.get(local_id)
        if created is None:
            raise RuntimeError(
                "Upload completed but no Drive file ID was returned."
            )

        return created
