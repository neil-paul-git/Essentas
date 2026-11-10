from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """SQLite hands back timezone-aware columns as naive datetimes (Postgres doesn't).
    Treat naive values as UTC so comparisons work on both."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
