"""Tests for web routes."""
import pytest


def test_dashboard_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Domani" in response.content
    assert b"No domains tracked" in response.content or b"Tracked Domains" in response.content


def test_add_domain_page(client):
    response = client.get("/domains/add")
    assert response.status_code == 200
    assert b"Add Domain" in response.content


def test_settings_page(client):
    response = client.get("/settings")
    assert response.status_code == 200
    assert b"Settings" in response.content
    assert b"SMTP" in response.content


def test_add_domain_invalid(client):
    response = client.post(
        "/domains",
        data={"name": "not a domain!!!"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_add_and_view_domain(client):
    response = client.post(
        "/domains",
        data={
            "name": "example.com",
            "watch_type": "snag",
            "notes": "Test domain",
            "check_interval_hours": "6",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"example.com" in response.content


def test_domain_detail_not_found(client):
    response = client.get("/domains/99999")
    assert response.status_code == 404


def test_404_page(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
