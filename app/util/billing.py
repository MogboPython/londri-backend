import calendar
from datetime import datetime, timedelta


def add_billing_interval(start: datetime, billing_cycle: str) -> datetime:
    """Advance `start` by one billing cycle. Calendar-correct for "monthly"
    (e.g. Jan 31 -> Feb 28), not just a fixed 30-day offset."""
    if billing_cycle == "weekly":
        return start + timedelta(days=7)

    if billing_cycle == "monthly":
        month = start.month + 1
        year = start.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(start.day, calendar.monthrange(year, month)[1])
        return start.replace(year=year, month=month, day=day)

    raise ValueError(f"Unsupported billing cycle: {billing_cycle}")
