from __future__ import annotations

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def to_jst(dt: datetime) -> datetime:
    """
    Convert a datetime to JST timezone-aware datetime.

    If dt is naive, it is treated as UTC by default to avoid ambiguity.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JST)


def is_within_range(dt: datetime, start: datetime, end: datetime) -> bool:
    """
    Check if dt is within [start, end) under timezone-aware comparisons.

    All datetimes are converted to JST before comparison.
    """
    dt_jst = to_jst(dt)
    start_jst = to_jst(start)
    end_jst = to_jst(end)
    return start_jst <= dt_jst < end_jst


def build_date_path(dt: datetime) -> str:
    """
    Build a date-based folder path string as 'YYYY/MM/DD' from datetime in JST.
    """
    dt_jst = to_jst(dt)
    return dt_jst.strftime("%Y/%m/%d")
