import enum


class RecurrenceFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class ReminderLeadTime(str, enum.Enum):
    FIFTEEN_MINUTES = "15_minutes"
    ONE_HOUR = "1_hour"
    ONE_DAY = "1_day"
    ONE_WEEK = "1_week"

    def as_timedelta(self):
        from datetime import timedelta

        return {
            ReminderLeadTime.FIFTEEN_MINUTES: timedelta(minutes=15),
            ReminderLeadTime.ONE_HOUR: timedelta(hours=1),
            ReminderLeadTime.ONE_DAY: timedelta(days=1),
            ReminderLeadTime.ONE_WEEK: timedelta(weeks=1),
        }[self]
