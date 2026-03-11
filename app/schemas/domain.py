from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
import re


def validate_domain_name(v: str) -> str:
    v = v.strip().lower()
    # Remove protocol if provided
    v = re.sub(r"^https?://", "", v)
    # Remove trailing slash and path
    v = v.split("/")[0]
    # Basic domain validation
    pattern = r"^(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
    if not re.match(pattern, v):
        raise ValueError(f"'{v}' is not a valid domain name")
    return v


class DomainCreate(BaseModel):
    name: str
    watch_type: str = "snag"
    notes: Optional[str] = None
    tags: Optional[str] = None
    check_interval_hours: int = 6

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_domain_name(v)

    @field_validator("watch_type")
    @classmethod
    def validate_watch_type(cls, v: str) -> str:
        if v not in ("own", "snag"):
            raise ValueError("watch_type must be 'own' or 'snag'")
        return v


class DomainUpdate(BaseModel):
    watch_type: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[str] = None
    check_interval_hours: Optional[int] = None


class DomainResponse(BaseModel):
    id: int
    name: str
    status: str
    registrar: Optional[str] = None
    expires_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    watch_type: str
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
