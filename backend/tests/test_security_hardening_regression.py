"""
Security Hardening Regression Test Suite.
Verifies authentication, IDOR, regex injection, and enumeration fixes.
"""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from apps.authentication.password import hash_password
from apps.authentication.repository import UserRepository
from apps.common.base_repository import BaseRepository
from apps.database.connection import reset_mock_db_for_testing


@pytest.fixture(autouse=True)
def isolated_mock_db():
    reset_mock_db_for_testing()
    yield
    reset_mock_db_for_testing()


@pytest.fixture
def api_client():
    return APIClient()


def test_hardcoded_demo_password_backdoor_removed(api_client):
    """Demo accounts must reject hardcoded fallback passwords like password123."""
    UserRepository().create_user(
        email="admin@bizpermit.gov.in",
        password_hash=hash_password("RealStrongAdminPass!99"),
        full_name="Platform Admin",
        role="SUPER_ADMIN",
    )

    for backdoor_pw in ("password123", "password123!", "securepass123!"):
        res = api_client.post(
            "/api/v1/auth/login",
            {"email": "admin@bizpermit.gov.in", "password": backdoor_pw},
            format="json",
        )
        assert res.status_code == 401

    ok = api_client.post(
        "/api/v1/auth/login",
        {"email": "admin@bizpermit.gov.in", "password": "RealStrongAdminPass!99"},
        format="json",
    )
    assert ok.status_code == 200


@override_settings(AUTO_SEED_DEMO_DATA=False)
def test_login_does_not_auto_seed_when_disabled(api_client):
    """Unauthenticated login must not trigger demo seeding when AUTO_SEED_DEMO_DATA is False."""
    res = api_client.post(
        "/api/v1/auth/login",
        {"email": "admin@bizpermit.gov.in", "password": "Admin@12345"},
        format="json",
    )
    assert res.status_code == 401
    assert UserRepository().find_by_email("admin@bizpermit.gov.in") is None


def test_forgot_password_prevents_email_enumeration(api_client):
    """Forgot-password must return identical response shape for existing and non-existing emails."""
    api_client.post(
        "/api/v1/auth/register",
        {
            "email": "existing.owner@example.com",
            "password": "StrongPassword!123",
            "full_name": "Existing Owner",
            "phone_number": "+919800000001",
        },
        format="json",
    )

    res_existing = api_client.post(
        "/api/v1/auth/forgot-password",
        {"email": "existing.owner@example.com"},
        format="json",
    )
    res_missing = api_client.post(
        "/api/v1/auth/forgot-password",
        {"email": "nobody@example.com"},
        format="json",
    )

    assert res_existing.status_code == 200
    assert res_missing.status_code == 200
    assert "reset_sent" not in res_existing.json()["data"]
    assert "reset_url" not in res_existing.json()["data"]
    assert res_existing.json()["data"]["reset_requested"] is True
    assert res_missing.json()["data"]["reset_requested"] is True


def test_confirm_upload_blocks_cross_tenant_path_and_traversal(api_client):
    """confirm-upload must reject storage_object_path outside the caller's business prefix or with traversal."""
    reg_a = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "owner.a@example.com",
            "password": "StrongPassword!123",
            "full_name": "Owner A",
            "phone_number": "+919800000011",
        },
        format="json",
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_a}")

    biz_a = api_client.post(
        "/api/v1/businesses",
        {
            "legal_name": "Alpha Manufacturing Pvt Ltd",
            "entity_type": "PRIVATE_LIMITED",
            "pan": "ABCDE1234F",
        },
        format="json",
    ).json()["data"]

    for malicious_path in (
        "businesses/000000000000000000000099/docs/victim_secret.pdf",
        f"businesses/{biz_a['id']}/docs/../../other_biz/secret.pdf",
        f"businesses/{biz_a['id']}/docs/",
    ):
        res = api_client.post(
            "/api/v1/documents/confirm-upload",
            {
                "business_id": biz_a["id"],
                "document_name": "Stolen Doc",
                "document_category": "FACTORY_LAYOUT",
                "original_filename": "secret.pdf",
                "storage_object_path": malicious_path,
            },
            format="json",
        )
        assert res.status_code == 403


def test_safe_regex_escapes_metacharacters_and_bounds_length():
    """BaseRepository.safe_regex must escape ReDoS/wildcard patterns and bound length."""
    evil = "(a+)+$" * 30
    res = BaseRepository.safe_regex(evil)
    assert res is not None
    assert len(res["$regex"]) <= 200  # escaped bounded string
    assert res["$options"] == "i"
    assert BaseRepository.safe_regex("   ") is None
    assert BaseRepository.safe_regex("foo.*bar")["$regex"] == r"foo\.\*bar"


def test_jwt_logout_revokes_access_and_refresh_tokens(api_client):
    """Logged-out access and refresh tokens must be rejected immediately."""
    reg = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "logout.user@example.com",
            "password": "StrongPassword!123",
            "full_name": "Logout User",
            "phone_number": "+919800000022",
        },
        format="json",
    )
    tokens = reg.json()["data"]["tokens"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")

    assert api_client.get("/api/v1/auth/me").status_code == 200
    logout_res = api_client.post(
        "/api/v1/auth/logout",
        {"refresh_token": tokens["refresh_token"]},
        format="json",
    )
    assert logout_res.status_code == 200

    assert api_client.get("/api/v1/auth/me").status_code == 401
    refresh_res = api_client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": tokens["refresh_token"]},
        format="json",
    )
    assert refresh_res.status_code == 401
