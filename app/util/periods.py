from datetime import date, datetime, time, timedelta, timezone
from enum import Enum

from fastapi import HTTPException, status


class Period(str, Enum):
    today = "today"
    this_week = "this_week"
    this_month = "this_month"
    last_3_months = "last_3_months"
    all_time = "all_time"
    custom = "custom"


def resolve_period_range(
    period: Period,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Resolve a `Period` into a concrete [start, end] UTC datetime range."""
    now = datetime.now(timezone.utc)

    if period == Period.custom:
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_date and end_date are required for a custom period.",
            )
        return (
            datetime.combine(start_date, time.min, tzinfo=timezone.utc),
            datetime.combine(end_date, time.max, tzinfo=timezone.utc),
        )

    if period == Period.all_time:
        return None, None

    if period == Period.today:
        return datetime.combine(now.date(), time.min, tzinfo=timezone.utc), now

    if period == Period.this_week:
        start_of_week = now.date() - timedelta(days=now.weekday())
        return datetime.combine(start_of_week, time.min, tzinfo=timezone.utc), now

    if period == Period.this_month:
        return datetime.combine(now.date().replace(day=1), time.min, tzinfo=timezone.utc), now

    if period == Period.last_3_months:
        return now - timedelta(days=90), now

    return None, None
