"""Shared Jinja2 templates instance with all custom filters and globals."""
from datetime import datetime, timezone
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def time_ago(dt: datetime) -> str:
    if dt is None:
        return "never"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    if delta.days > 365:
        return f"{delta.days // 365}y ago"
    if delta.days > 30:
        return f"{delta.days // 30}mo ago"
    if delta.days > 0:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours}h ago"
    minutes = delta.seconds // 60
    if minutes > 0:
        return f"{minutes}m ago"
    return "just now"


def days_countdown(dt: datetime) -> str:
    if dt is None:
        return "Unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = dt - datetime.now(timezone.utc)
    days = delta.days
    if days < 0:
        return f"{abs(days)}d ago"
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days"


def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(fmt)


# Register filters
templates.env.filters["time_ago"] = time_ago
templates.env.filters["days_countdown"] = days_countdown
templates.env.filters["format_date"] = format_date

# Register globals
from .models.domain import DomainStatus, STATUS_LABELS
from .config import settings as app_settings

templates.env.globals["DomainStatus"] = DomainStatus
templates.env.globals["STATUS_LABELS"] = STATUS_LABELS
templates.env.globals["app_version"] = app_settings.app_version
