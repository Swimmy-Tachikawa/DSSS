from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from gdrivemgr import AuthInfo, GoogleDriveManager


@dataclass
class UploadTarget:
    """Represents one local file selected for upload."""

    path: Path
    modified_time: datetime


@dataclass
class UploadSummary:
    """Represents upload execution summary."""

    local_directory: Path
    student_name: str
    upload_date_folder: str
    shared_data_folder_name: str
    selected_files: List[UploadTarget]
    uploaded_count: int


class StudentTimedUploader:
    """Upload files updated in a time range into a student/date folder."""

    SHARED_DATA_FOLDER_NAME = "共有データ"

    def __init__(
        self,
        auth: AuthInfo,
        root_folder_id: str,
    ) -> None:
        self._manager = GoogleDriveManager(auth)
        self._root_folder_id = root_folder_id
        self._local = self._manager.open(root_folder_id)

    def upload_updated_files(
        self,
        local_directory: str | Path,
        start_time: datetime,
        end_time: datetime,
        upload_date: Optional[date] = None,
    ) -> UploadSummary:
        """
        Upload files updated within [start_time, end_time].

        Args:
            local_directory: Local directory path.
            start_time: Start datetime.
            end_time: End datetime.
            upload_date: Folder date. If omitted, today's date is used.

        Returns:
            UploadSummary: Execution summary.
        """
        directory = Path(local_directory)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        if start_time > end_time:
            raise ValueError("start_time must be earlier than or equal to end_time")

        targets = self._collect_targets(directory, start_time, end_time)

        student_name = self._select_student()

        student_folder_id = self._find_child_folder_id(
            parent_id=self._root_folder_id,
            folder_name=student_name,
        )
        if student_folder_id is None:
            raise ValueError(f"Student folder not found: {student_name}")

        upload_date_value = upload_date or date.today()
        upload_date_folder_name = upload_date_value.strftime("%Y/%m/%d")

        date_folder_id = self._find_or_create_folder(
            parent_id=student_folder_id,
            folder_name=upload_date_folder_name,
        )

        for target in targets:
            if target.path.name in map(lambda x: x.name, self._local.list_children(date_folder_id)):
                continue
            self._local.upload_file(str(target.path), date_folder_id)

        plan = self._manager.build_plan()
        self._manager.apply_plan(plan)

        return UploadSummary(
            local_directory=directory,
            student_name=student_name,
            upload_date_folder=upload_date_folder_name,
            shared_data_folder_name=self.SHARED_DATA_FOLDER_NAME,
            selected_files=targets,
            uploaded_count=len(targets),
        )

    def _select_student(self) -> str:
        """ Select student directory name that upload files. """
        student_names = tuple(map(lambda x: x.name, self._local.list_children(self._root_folder_id)))

        done = False
        while not done:

            key = input("生徒検索(名前のキーワードを入力): ")
            match_names = []
            for student_name in student_names:
                if key not in student_name:
                    continue
                match_names.append(student_name)
                continue

            if len(match_names) == 0:
                print("キーワードに従う生徒が見つかりませんでした")
                continue

            print("生徒候補")
            for idx, student_name in enumerate(match_names):
                print(f"{idx}: {student_name}")
                continue

            target_idx = input("対象生徒のidx値を入力: ")
            try:
                target_idx = int(target_idx)
                target_name = match_names[target_idx]
            except ValueError as e:
                print("数値以外が入力されました")
            except IndexError as e:
                print("範囲外のidx値が入力されました")
            else:
                done = target_name in match_names

            continue

        return target_name

    def _collect_targets(
        self,
        directory: Path,
        start_time: datetime,
        end_time: datetime,
    ) -> List[UploadTarget]:
        """Collect files updated within the given time range."""
        targets: List[UploadTarget] = []

        for path in directory.iterdir():
            if not path.is_file():
                continue

            modified_time = datetime.fromtimestamp(path.stat().st_mtime)
            if start_time <= modified_time <= end_time:
                targets.append(
                    UploadTarget(
                        path=path,
                        modified_time=modified_time,
                    )
                )

        return sorted(targets, key=lambda item: item.modified_time)

    def _find_or_create_folder(self, parent_id: str, folder_name: str) -> str:
        """Find a folder by name under parent, or create it."""
        folder_id = self._find_child_folder_id(parent_id, folder_name)
        if folder_id is not None:
            return folder_id

        return self._local.create_folder(folder_name, parent_id)

    def _find_child_folder_id(
        self,
        parent_id: str,
        folder_name: str,
    ) -> Optional[str]:
        """Find a direct child folder ID by name."""
        result = self._local.find_by_name(folder_name, parent_id)
        if len(result) == 0: return None
        return result[0].file_id
