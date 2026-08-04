import calendar as calendar_module
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.modules.calendar.enums import RecurrenceFrequency


def to_utc_naive(dt: datetime) -> datetime:
    """Normalizes a datetime for arithmetic/comparison. SQLite doesn't persist
    tzinfo, so a value read back from the DB can be naive even though it was
    written as UTC-aware - treat naive values as already UTC and strip tzinfo
    from aware ones, so every comparison in this module is apples-to-apples."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def parse_weekdays(value: str | None) -> list[int] | None:
    """Parses a comma-separated weekday list (Monday=0..Sunday=6)."""
    if not value:
        return None
    return [int(x) for x in value.split(",") if x.strip() != ""]


def format_weekdays(weekdays: list[int] | None) -> str | None:
    if not weekdays:
        return None
    return ",".join(str(w) for w in weekdays)


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar_module.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _add_years(dt: datetime, years: int) -> datetime:
    year = dt.year + years
    day = min(dt.day, calendar_module.monthrange(year, dt.month)[1])
    return dt.replace(year=year, day=day)


@dataclass
class Occurrence:
    occurrence_date: date
    start_at: datetime
    end_at: datetime
    is_exception: bool
    source_event_id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    is_completed: bool


def _occurrence_start_dates(event, range_start: datetime, range_end: datetime) -> list[datetime]:
    """Pure date math: which occurrence start datetimes does this event's
    recurrence rule land on within [range_start, range_end)? Bounded so a
    forever-recurring event never generates more than the requested window."""
    start = to_utc_naive(event.start_at)

    if event.recurrence_frequency is None:
        return [start] if range_start <= start < range_end else []

    interval = max(event.recurrence_interval, 1)
    recurrence_end = None
    if event.recurrence_end_date is not None:
        recurrence_end = datetime.combine(event.recurrence_end_date, datetime.max.time())

    starts: list[datetime] = []

    if event.recurrence_frequency == RecurrenceFrequency.DAILY:
        cursor = start
        while cursor < range_end and (recurrence_end is None or cursor <= recurrence_end):
            if cursor >= range_start:
                starts.append(cursor)
            cursor = cursor + timedelta(days=interval)

    elif event.recurrence_frequency == RecurrenceFrequency.WEEKLY:
        weekdays = parse_weekdays(event.recurrence_by_weekday) or [start.weekday()]
        week_anchor_date = start.date() - timedelta(days=start.weekday())
        total_weeks = max((range_end.date() - week_anchor_date).days // 7 + 2, 1)
        for week_index in range(0, total_weeks, interval):
            for weekday in weekdays:
                candidate = datetime.combine(week_anchor_date + timedelta(weeks=week_index, days=weekday), start.time())
                if candidate < start:
                    continue
                if recurrence_end is not None and candidate > recurrence_end:
                    continue
                if range_start <= candidate < range_end:
                    starts.append(candidate)

    elif event.recurrence_frequency == RecurrenceFrequency.MONTHLY:
        cursor = start
        i = 0
        while cursor < range_end and (recurrence_end is None or cursor <= recurrence_end):
            if cursor >= range_start:
                starts.append(cursor)
            i += 1
            cursor = _add_months(start, interval * i)

    elif event.recurrence_frequency == RecurrenceFrequency.YEARLY:
        cursor = start
        i = 0
        while cursor < range_end and (recurrence_end is None or cursor <= recurrence_end):
            if cursor >= range_start:
                starts.append(cursor)
            i += 1
            cursor = _add_years(start, interval * i)

    return sorted(starts)


def expand_event(event, exceptions: list, range_start: datetime, range_end: datetime) -> list[Occurrence]:
    """Expands `event` (a base/series row - never itself an exception) into
    individual occurrences overlapping [range_start, range_end). `exceptions`
    are this event's own child rows (parent_event_id == event.id); each one
    overrides or cancels a single occurrence_date."""
    start = to_utc_naive(event.start_at)
    end = to_utc_naive(event.end_at)
    duration = end - start
    range_start = to_utc_naive(range_start)
    range_end = to_utc_naive(range_end)

    exceptions_by_date = {exc.occurrence_date: exc for exc in exceptions}

    occurrences: list[Occurrence] = []
    for occ_start in _occurrence_start_dates(event, range_start, range_end):
        occ_date = occ_start.date()
        exc = exceptions_by_date.get(occ_date)
        if exc is not None:
            if exc.is_cancelled:
                continue
            occurrences.append(
                Occurrence(
                    occurrence_date=occ_date,
                    start_at=to_utc_naive(exc.start_at),
                    end_at=to_utc_naive(exc.end_at),
                    is_exception=True,
                    source_event_id=exc.id,
                    title=exc.title,
                    description=exc.description,
                    location=exc.location,
                    is_completed=exc.is_completed,
                )
            )
        else:
            occurrences.append(
                Occurrence(
                    occurrence_date=occ_date,
                    start_at=occ_start,
                    end_at=occ_start + duration,
                    is_exception=False,
                    source_event_id=event.id,
                    title=event.title,
                    description=event.description,
                    location=event.location,
                    is_completed=event.is_completed,
                )
            )
    return occurrences
