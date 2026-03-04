from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from dsss.errors import LocalScanError
from dsss.timeutils import is_within_range, to_jst
from dsss.types import LocalFile, LocalScanResult


def _iter_direct_children(source_dir: Path) -> Iterable[Path]:
    """
    Yield direct children of a directory.

    This function exists to make testing and error handling clearer.
    """
    try:
        yield from source_dir.iterdir()
    except OSError as exc:
        raise LocalScanError(f"Failed to list directory: {source_dir}") from exc


def scan_local_files(
    source_dir: Path | str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> LocalScanResult:
    """
    Scan only the direct children of source_dir and return file metadata.

    Rules:
    - Only direct children (no recursion)
    - Exclude directories
    - Exclude symlinks
    - If start/end are provided, filter by mtime within [start, end) in JST
    """
    src = Path(source_dir).expanduser().resolve()
    if not src.exists() or not src.is_dir():
        raise LocalScanError(f"source_dir is not a directory: {src}")

    files: list[LocalFile] = []

    for child in _iter_direct_children(src):
        # Exclude symlinks
        if child.is_symlink():
            continue

        # Exclude directories
        if child.is_dir():
            continue

        if not child.is_file():
            continue

        try:
            stat = child.stat()
        except OSError as exc:
            raise LocalScanError(f"Failed to stat file: {child}") from exc

        mtime_utc = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        mtime_jst = to_jst(mtime_utc)

        if start is not None and end is not None:
            if not is_within_range(mtime_jst, start, end):
                continue
        elif start is not None or end is not None:
            raise LocalScanError("Both start and end must be provided together.")

        files.append(
            LocalFile(
                path=child,
                name=child.name,
                size_bytes=int(stat.st_size),
                mtime_jst=mtime_jst,
            )
        )

    files_sorted = tuple(sorted(files, key=lambda f: f.mtime_jst))
    return LocalScanResult(files=files_sorted)
