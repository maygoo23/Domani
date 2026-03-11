import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..database import Base


class EventType(str, enum.Enum):
    WHOIS_CHECK = "whois_check"
    STATUS_CHANGE = "status_change"
    ALERT_SENT = "alert_sent"
    ALERT_FAILED = "alert_failed"
    MANUAL_REFRESH = "manual_refresh"
    DOMAIN_ADDED = "domain_added"
    DOMAIN_UPDATED = "domain_updated"
    ERROR = "error"


EVENT_ICONS = {
    EventType.WHOIS_CHECK: ("fa-magnifying-glass", "text-info"),
    EventType.STATUS_CHANGE: ("fa-arrow-right-arrow-left", "text-warning"),
    EventType.ALERT_SENT: ("fa-bell", "text-success"),
    EventType.ALERT_FAILED: ("fa-bell-slash", "text-danger"),
    EventType.MANUAL_REFRESH: ("fa-rotate", "text-primary"),
    EventType.DOMAIN_ADDED: ("fa-plus", "text-success"),
    EventType.DOMAIN_UPDATED: ("fa-pen", "text-secondary"),
    EventType.ERROR: ("fa-triangle-exclamation", "text-danger"),
}


class DomainEvent(Base):
    __tablename__ = "domain_events"

    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True)  # noqa: E501
    event_type = Column(String(64), nullable=False)
    old_status = Column(String(32), nullable=True)
    new_status = Column(String(32), nullable=True)
    message = Column(Text, nullable=True)
    raw_whois = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    domain = relationship("Domain", back_populates="events")

    @property
    def icon(self) -> tuple[str, str]:
        return EVENT_ICONS.get(EventType(self.event_type), ("fa-circle-info", "text-secondary"))
