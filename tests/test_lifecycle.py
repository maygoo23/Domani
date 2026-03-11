"""Tests for domain lifecycle state machine."""
from datetime import datetime, timezone, timedelta
import pytest

from app.models.domain import DomainStatus
from app.services.domain_lifecycle import determine_status, is_alert_worthy_transition
from app.services.whois_service import WhoisResult


def make_result(expires_in_days=None, error=None, registrar="Test Registrar", status_codes=None):
    expires_at = None
    if expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    return WhoisResult(
        domain="example.com",
        registrar=registrar if not error else None,
        expires_at=expires_at,
        status_codes=status_codes or [],
        error=error,
    )


class TestDetermineStatus:
    def test_error_result(self):
        result = make_result(error="Connection timeout")
        assert determine_status(result, "example.com") == DomainStatus.ERROR

    def test_not_registered_is_available(self):
        result = WhoisResult(domain="example.com")  # no registrar, no expiry
        assert determine_status(result, "example.com") == DomainStatus.AVAILABLE

    def test_active_domain(self):
        result = make_result(expires_in_days=180)
        assert determine_status(result, "example.com") == DomainStatus.ACTIVE

    def test_expiring_soon(self):
        result = make_result(expires_in_days=25)
        assert determine_status(result, "example.com") == DomainStatus.EXPIRING_SOON

    def test_expiring_critical(self):
        result = make_result(expires_in_days=3)
        assert determine_status(result, "example.com") == DomainStatus.EXPIRING_CRITICAL

    def test_expired(self):
        result = make_result(expires_in_days=-10)
        assert determine_status(result, "example.com") == DomainStatus.EXPIRED

    def test_pending_delete_epp_code(self):
        result = make_result(expires_in_days=-35, status_codes=["pendingDelete"])
        assert determine_status(result, "example.com") == DomainStatus.PENDING_DELETE

    def test_redemption_epp_code(self):
        result = make_result(expires_in_days=-10, status_codes=["redemptionPeriod"])
        assert determine_status(result, "example.com") == DomainStatus.REDEMPTION

    def test_active_no_expiry(self):
        result = make_result(expires_in_days=None)
        assert determine_status(result, "example.com") == DomainStatus.ACTIVE


class TestAlertWorthyTransitions:
    def test_active_to_expiring_soon(self):
        assert is_alert_worthy_transition("active", "expiring_soon")

    def test_pending_delete_to_available(self):
        assert is_alert_worthy_transition("pending_delete", "available")

    def test_none_old_status(self):
        assert not is_alert_worthy_transition(None, "expiring_soon")

    def test_no_change_not_worthy(self):
        assert not is_alert_worthy_transition("active", "active")
