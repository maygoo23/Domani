import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from ..database import Base


class DomainStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRING_CRITICAL = "expiring_critical"
    EXPIRED = "expired"
    REDEMPTION = "redemption"
    PENDING_DELETE = "pending_delete"
    AVAILABLE = "available"
    ERROR = "error"


FAST_POLL_STATES = {DomainStatus.REDEMPTION, DomainStatus.PENDING_DELETE}

STATUS_LABELS = {
    DomainStatus.UNKNOWN: ("Unknown", "secondary"),
    DomainStatus.ACTIVE: ("Active", "success"),
    DomainStatus.EXPIRING_SOON: ("Expiring Soon", "warning"),
    DomainStatus.EXPIRING_CRITICAL: ("Critical", "danger"),
    DomainStatus.EXPIRED: ("Expired", "danger"),
    DomainStatus.REDEMPTION: ("Redemption Period", "purple"),
    DomainStatus.PENDING_DELETE: ("Pending Delete", "dark-red"),
    DomainStatus.AVAILABLE: ("Available!", "info"),
    DomainStatus.ERROR: ("Check Error", "secondary"),
}


class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    status = Column(String(32), default=DomainStatus.UNKNOWN, index=True)

    # WHOIS data
    registrar = Column(String(255), nullable=True)
    registrant = Column(String(255), nullable=True)
    registered_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    name_servers = Column(Text, nullable=True)  # JSON list

    # Tracking metadata
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_check_error = Column(Text, nullable=True)
    check_interval_hours = Column(Integer, default=6)
    fast_poll_enabled = Column(Boolean, default=False)
    consecutive_errors = Column(Integer, default=0)

    # User metadata
    notes = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)
    watch_type = Column(String(16), default="snag")  # "own" or "snag"

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    alert_configs = relationship("AlertConfig", back_populates="domain", cascade="all, delete-orphan")  # noqa: E501
    events = relationship(
        "DomainEvent",
        back_populates="domain",
        cascade="all, delete-orphan",
        order_by="DomainEvent.created_at.desc()",
    )

    @property
    def status_label(self) -> tuple[str, str]:
        return STATUS_LABELS.get(DomainStatus(self.status), ("Unknown", "secondary"))

    @property
    def days_until_expiry(self) -> int | None:
        if not self.expires_at:
            return None
        now = datetime.now(UTC)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        delta = expires - now
        return delta.days

    @property
    def tag_list(self) -> list[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]
