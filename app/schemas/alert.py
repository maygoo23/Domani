from typing import Optional
from pydantic import BaseModel, field_validator, EmailStr


VALID_METHODS = {"email", "webhook"}
VALID_EVENT_TYPES = {
    "expiring_soon", "expiring_critical", "expired",
    "redemption", "pending_delete", "available", "status_change"
}


class AlertConfigCreate(BaseModel):
    method: str
    target: str
    event_types: str = "expiring_soon,expiring_critical,pending_delete,available"
    webhook_secret: Optional[str] = None
    enabled: bool = True

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        if v not in VALID_METHODS:
            raise ValueError(f"method must be one of: {', '.join(VALID_METHODS)}")
        return v

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, v: str) -> str:
        types = [t.strip() for t in v.split(",") if t.strip()]
        for t in types:
            if t not in VALID_EVENT_TYPES:
                raise ValueError(f"'{t}' is not a valid event type")
        return ",".join(types)
