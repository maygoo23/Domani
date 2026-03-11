"""Tests for WHOIS normalization helpers."""
from datetime import datetime, timezone
import pytest

from app.services.whois_service import _normalize_datetime, _normalize_string, _normalize_list


class TestNormalizeDatetime:
    def test_none(self):
        assert _normalize_datetime(None) is None

    def test_list_takes_first(self):
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = _normalize_datetime([dt, datetime(2024, 1, 1, tzinfo=timezone.utc)])
        assert result == dt

    def test_naive_datetime_gets_utc(self):
        naive = datetime(2025, 6, 15)
        result = _normalize_datetime(naive)
        assert result.tzinfo == timezone.utc

    def test_aware_datetime_unchanged(self):
        aware = datetime(2025, 6, 15, tzinfo=timezone.utc)
        assert _normalize_datetime(aware) == aware

    def test_empty_list(self):
        assert _normalize_datetime([]) is None


class TestNormalizeString:
    def test_none(self):
        assert _normalize_string(None) is None

    def test_list(self):
        assert _normalize_string(["GoDaddy", "Other"]) == "GoDaddy"

    def test_empty_string(self):
        assert _normalize_string("") is None

    def test_whitespace(self):
        assert _normalize_string("  ") is None

    def test_strips(self):
        assert _normalize_string("  Namecheap  ") == "Namecheap"


class TestNormalizeList:
    def test_none(self):
        assert _normalize_list(None) == []

    def test_string(self):
        assert _normalize_list("ns1.example.com") == ["ns1.example.com"]

    def test_list(self):
        result = _normalize_list(["NS1.EXAMPLE.COM", "NS2.EXAMPLE.COM"])
        assert result == ["ns1.example.com", "ns2.example.com"]
