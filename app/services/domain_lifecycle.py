"""Domain lifecycle state machine logic."""
from datetime import UTC, datetime

from ..config import settings
from ..models.domain import DomainStatus
from ..services.whois_service import WhoisResult

# EPP status codes that indicate pending delete
PENDING_DELETE_CODES = {"pendingdelete", "pending-delete", "pending_delete"}
REDEMPTION_CODES = {"redemptionperiod", "redemption-period", "redemption_period"}
CLIENT_HOLD_CODES = {"clienthold", "client-hold"}
SERVER_HOLD_CODES = {"serverhold", "server-hold"}


def determine_status(result: WhoisResult, domain_name: str) -> DomainStatus:
    """
    Determine a domain's lifecycle status from WHOIS result.

    Priority order:
    1. Error state
    2. Not registered → available
    3. EPP status codes (most authoritative)
    4. Expiry date proximity
    """
    if result.error:
        return DomainStatus.ERROR

    # Domain is not registered
    if not result.is_registered:
        return DomainStatus.AVAILABLE

    now = datetime.now(UTC)

    # Check EPP status codes first (most authoritative)
    status_lower = {s.lower() for s in result.status_codes}

    for code in status_lower:
        clean = code.split()[0] if " " in code else code
        if clean in PENDING_DELETE_CODES:
            return DomainStatus.PENDING_DELETE
        if clean in REDEMPTION_CODES:
            return DomainStatus.REDEMPTION

    # Check expiry date
    if result.expires_at:
        expires = result.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)

        days_remaining = (expires - now).days

        if days_remaining < 0:
            # Past expiry — check if EPP codes suggest it's still in grace period
            # Without explicit codes, classify as expired
            return DomainStatus.EXPIRED
        elif days_remaining <= settings.expiring_critical_days:
            return DomainStatus.EXPIRING_CRITICAL
        elif days_remaining <= settings.expiring_soon_days:
            return DomainStatus.EXPIRING_SOON
        else:
            return DomainStatus.ACTIVE

    # Has registrar but no expiry date (some TLDs don't expose expiry in WHOIS)
    if result.registrar:
        return DomainStatus.ACTIVE

    return DomainStatus.UNKNOWN


# Transitions that should trigger alert dispatch
ALERT_WORTHY_TRANSITIONS: set[tuple[str, str]] = {
    (DomainStatus.ACTIVE, DomainStatus.EXPIRING_SOON),
    (DomainStatus.ACTIVE, DomainStatus.EXPIRING_CRITICAL),
    (DomainStatus.ACTIVE, DomainStatus.EXPIRED),
    (DomainStatus.EXPIRING_SOON, DomainStatus.EXPIRING_CRITICAL),
    (DomainStatus.EXPIRING_SOON, DomainStatus.EXPIRED),
    (DomainStatus.EXPIRING_CRITICAL, DomainStatus.EXPIRED),
    (DomainStatus.EXPIRED, DomainStatus.REDEMPTION),
    (DomainStatus.REDEMPTION, DomainStatus.PENDING_DELETE),
    (DomainStatus.PENDING_DELETE, DomainStatus.AVAILABLE),
    (DomainStatus.EXPIRED, DomainStatus.AVAILABLE),
    # Re-registration (someone snagged it or it was renewed)
    (DomainStatus.AVAILABLE, DomainStatus.ACTIVE),
    (DomainStatus.PENDING_DELETE, DomainStatus.ACTIVE),
}

# Statuses that should trigger expiry-day-based alerts regardless of transition
EXPIRY_ALERT_STATUSES = {DomainStatus.EXPIRING_SOON, DomainStatus.EXPIRING_CRITICAL}


def is_alert_worthy_transition(old_status: str | None, new_status: str) -> bool:
    """Return True if this status transition should trigger alerts."""
    if old_status is None:
        return False
    return (old_status, new_status) in ALERT_WORTHY_TRANSITIONS


def status_matches_event_type(status: str, event_types: list[str]) -> bool:
    """Check if a domain status matches any of the configured alert event types."""
    return status in event_types or "status_change" in event_types


def get_snagging_registrar_links(domain: str) -> list[dict[str, str]]:
    """Return direct registration/backorder links for popular registrars."""
    return [
        {"name": "Namecheap", "url": f"https://www.namecheap.com/domains/registration/results/?domain={domain}", "icon": "🐦"},  # noqa: E501
        {"name": "Porkbun", "url": f"https://porkbun.com/checkout/search?q={domain}", "icon": "🐷"},
        {"name": "Cloudflare", "url": "https://www.cloudflare.com/products/registrar/", "icon": "🌩️"},  # noqa: E501
        {"name": "GoDaddy", "url": f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}", "icon": "🐢"},  # noqa: E501
        {"name": "Dynadot", "url": f"https://www.dynadot.com/domain/search.html?domain={domain}", "icon": "🔍"},  # noqa: E501
        {"name": "SnapNames", "url": f"https://www.snapnames.com/showDomain.action?domain={domain}", "icon": "📸"},  # noqa: E501
    ]
