from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, Text

from ..database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))  # noqa: E501
