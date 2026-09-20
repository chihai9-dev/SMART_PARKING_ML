"""Tính phạt gửi xe quá số giờ so với thời lượng / nhóm dự đoán."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union

GRACE_MINUTES = 15

# (số phút vượt sau ân hạn, số tiền VND)
PENALTY_TIERS = [
    (30, 5_000),
    (120, 15_000),
    (360, 30_000),
]


def _to_dt(value: Union[str, datetime, None]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(text)


def compute_penalty(
    *,
    predicted_minutes: int,
    actual_minutes: Optional[int] = None,
    entry_time: Union[str, datetime, None] = None,
    exit_time: Union[str, datetime, None] = None,
    grace_minutes: int = GRACE_MINUTES,
) -> dict[str, Any]:
    """
    Phút vượt = thời gian gửi thực tế − thời lượng dự đoán.
    Trong khoảng ân hạn (mặc định 15 phút) thì không phạt.
    """
    if actual_minutes is None:
        start, end = _to_dt(entry_time), _to_dt(exit_time)
        if start is None or end is None:
            raise ValueError("Cần actual_minutes hoặc cặp entry_time/exit_time.")
        actual_minutes = max(0, int((end - start).total_seconds() // 60))

    predicted_minutes = int(predicted_minutes)
    overtime = max(0, actual_minutes - predicted_minutes)
    billable = max(0, overtime - grace_minutes)

    penalty = 0
    if billable > 0:
        penalty = PENALTY_TIERS[-1][1]
        for limit, amount in PENALTY_TIERS:
            if billable <= limit:
                penalty = amount
                break

    return {
        "actual_minutes": actual_minutes,
        "predicted_minutes": predicted_minutes,
        "overtime_minutes": overtime,
        "grace_minutes": grace_minutes,
        "billable_overtime_minutes": billable,
        "penalty_vnd": penalty,
        "is_overtime": overtime > grace_minutes,
    }
