import enum


class AccountType(str, enum.Enum):
    BANK = "bank"
    CASH = "cash"
    WALLET = "wallet"
    CREDIT_CARD = "credit_card"
    OTHER = "other"


class CategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class BillCadence(str, enum.Enum):
    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class BillType(str, enum.Enum):
    BILL = "bill"
    INCOME = "income"


class BillStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class BillReminderOffset(str, enum.Enum):
    """When a bill reminder fires, relative to the bill's due date - paired
    with a specific time-of-day (Reminder.remind_time) since a bill's due
    date alone has no time component."""

    SAME_DAY = "same_day"
    ONE_DAY_BEFORE = "one_day_before"
    ONE_WEEK_BEFORE = "one_week_before"
