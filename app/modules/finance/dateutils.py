import calendar
from datetime import date, timedelta

from app.modules.finance.enums import BillCadence


def parse_month(value: str) -> date:
    """Parses a "YYYY-MM" string into the first-of-month date used to key
    budgets and filter transactions/overviews by month."""
    try:
        year_str, month_str = value.split("-")
        return date(int(year_str), int(month_str), 1)
    except (ValueError, AttributeError) as exc:
        raise ValueError("month must be in YYYY-MM format") from exc


def month_range(month: date) -> tuple[date, date]:
    """Returns [start, end) for the calendar month containing `month`."""
    start = date(month.year, month.month, 1)
    end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return start, end


def parse_year(value: str) -> date:
    """Parses a "YYYY" string into the Jan-1 date used to key a yearly
    overview filter, mirroring parse_month's "YYYY-MM" handling."""
    try:
        return date(int(value), 1, 1)
    except (ValueError, AttributeError) as exc:
        raise ValueError("year must be in YYYY format") from exc


def year_range(year: date) -> tuple[date, date]:
    """Returns [start, end) for the calendar year containing `year`."""
    start = date(year.year, 1, 1)
    end = date(year.year + 1, 1, 1)
    return start, end


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def advance_due_date(current: date, cadence: BillCadence) -> date:
    """Computes the next occurrence of a recurring bill's due date from its
    current one. Month/year advances clamp the day to the target month's
    length (e.g. Jan 31 monthly -> Feb 28/29, not an error). ONE_TIME has no
    next cycle - it returns the same date, and the caller (complete_bill)
    ends the bill instead of leaving it "due" again."""
    if cadence == BillCadence.ONE_TIME:
        return current
    if cadence == BillCadence.DAILY:
        return current + timedelta(days=1)
    if cadence == BillCadence.WEEKLY:
        return current + timedelta(days=7)
    if cadence == BillCadence.MONTHLY:
        return _add_months(current, 1)
    if cadence == BillCadence.YEARLY:
        return _add_months(current, 12)
    raise ValueError(f"Unsupported cadence: {cadence}")
