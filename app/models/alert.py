from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False)

    # What events trigger this alert
    # Comma-separated DomainStatus values, e.g. "expiring_soon,expiring_critical,pending_delete"
    event_types = Column(String(500), nullable=False, default="expiring_soon,expiring_critical,pending_delete,available")  # noqa: E501

    # Delivery method
    method = Column(String(16), nullable=False)  # "email" or "webhook"
    target = Column(String(500), nullable=False)  # email address or webhook URL

    # Webhook signing secret
    webhook_secret = Column(String(128), nullable=True)

    enabled = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    domain = relationship("Domain", back_populates="alert_configs")

    @property
    def event_type_list(self) -> list[str]:
        if not self.event_types:
            return []
        return [e.strip() for e in self.event_types.split(",") if e.strip()]

    @property
    def method_icon(self) -> str:
        return "fa-envelope" if self.method == "email" else "fa-webhook"
