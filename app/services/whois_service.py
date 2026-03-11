"""WHOIS lookup service with retry logic, timeout, and result normalization."""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import whois

from ..config import settings

logger = logging.getLogger(__name__)

# Rate limiting: track last lookup time per thread
_last_lookup_time: float = 0.0
_lookup_lock = asyncio.Lock()


@dataclass
class WhoisResult:
    domain: str
    registrar: str | None = None
    registrant: str | None = None
    registered_at: datetime | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None
    name_servers: list[str] = field(default_factory=list)
    status_codes: list[str] = field(default_factory=list)
    raw: str = ""
    error: str | None = None

    @property
    def is_registered(self) -> bool:
        return self.expires_at is not None or bool(self.registrar)


def _normalize_datetime(value) -> datetime | None:
    """Normalize whois date values (may be list, datetime, or None)."""
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    return None


def _normalize_string(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _normalize_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if v]
    return []


def _do_whois_lookup(domain: str) -> WhoisResult:
    """Perform synchronous WHOIS lookup."""
    try:
        w = whois.whois(domain)
        if w is None:
            return WhoisResult(domain=domain, error="No WHOIS data returned")

        result = WhoisResult(
            domain=domain,
            registrar=_normalize_string(w.registrar),
            registrant=_normalize_string(getattr(w, "registrant_name", None) or getattr(w, "org", None)),  # noqa: E501
            registered_at=_normalize_datetime(w.creation_date),
            expires_at=_normalize_datetime(w.expiration_date),
            updated_at=_normalize_datetime(w.updated_date),
            name_servers=_normalize_list(w.name_servers),
            status_codes=_normalize_list(w.status),
            raw=str(w),
        )
        return result

    except whois.parser.PywhoisError as e:
        error_msg = str(e)
        # "No match" means domain is available
        if "no match" in error_msg.lower() or "not found" in error_msg.lower():
            return WhoisResult(domain=domain, raw=error_msg)  # no error, just not registered
        return WhoisResult(domain=domain, error=error_msg)
    except Exception as e:
        return WhoisResult(domain=domain, error=f"{type(e).__name__}: {e}")


async def lookup_domain(domain: str) -> WhoisResult:
    """Async WHOIS lookup with rate limiting and retry."""
    global _last_lookup_time

    last_result: WhoisResult | None = None

    for attempt in range(settings.whois_retry_count):
        async with _lookup_lock:
            # Rate limiting
            elapsed = time.monotonic() - _last_lookup_time
            if elapsed < settings.whois_rate_limit_seconds:
                await asyncio.sleep(settings.whois_rate_limit_seconds - elapsed)
            _last_lookup_time = time.monotonic()

        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _do_whois_lookup, domain),
                timeout=settings.whois_timeout_seconds,
            )
            if result.error is None:
                return result
            last_result = result
            logger.warning("WHOIS attempt %d/%d failed for %s: %s", attempt + 1, settings.whois_retry_count, domain, result.error)  # noqa: E501

        except TimeoutError:
            last_result = WhoisResult(domain=domain, error=f"Timeout after {settings.whois_timeout_seconds}s")  # noqa: E501
            logger.warning("WHOIS timeout on attempt %d/%d for %s", attempt + 1, settings.whois_retry_count, domain)  # noqa: E501

        if attempt < settings.whois_retry_count - 1:
            backoff = 2 ** attempt
            await asyncio.sleep(backoff)

    return last_result or WhoisResult(domain=domain, error="All WHOIS attempts failed")
