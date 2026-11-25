"""
Production Readiness, Health Probes, Observability & Log Redaction Tests.
"""

import logging
from unittest.mock import patch
import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from apps.common.middleware import SensitiveDataFilter, redact_sensitive_text
from apps.database.connection import reset_mock_db_for_testing


@pytest.fixture(autouse=True)
def isolated_db():
    reset_mock_db_for_testing()
    yield
    reset_mock_db_for_testing()


@pytest.fixture
def api_client():
    return APIClient()


def test_health_live_and_ready_endpoints(api_client):
    """Health, liveness, and readiness probes return 200 and correlation/timing headers."""
    res_health = api_client.get("/api/v1/health", HTTP_X_REQUEST_ID="trace_health_001")
    assert res_health.status_code == 200
    assert res_health["X-Request-ID"] == "trace_health_001"
    assert float(res_health["X-Response-Time-Ms"]) >= 0.0
    body = res_health.json()
    assert body["success"] is True
    assert body["meta"]["request_id"] == "trace_health_001"
    assert body["data"]["database_health"]["status"] == "connected"
    assert "storage_health" in body["data"]

    res_live = api_client.get("/api/v1/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["data"]["status"] == "alive"

    res_ready = api_client.get("/api/v1/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["data"]["status"] == "ready"


def test_health_returns_503_when_mongodb_unavailable_but_live_stays_200(api_client):
    """When MongoDB is disconnected, /health and /health/ready return 503 while /health/live stays 200."""
    disconnected = {
        "status": "disconnected",
        "mode": "live_mongodb",
        "database": "bizpermit_db",
        "replica_set_transactions_supported": False,
        "notes": "Database connectivity check failed",
    }
    with patch("bizpermit_core.urls.check_connection_health", return_value=disconnected):
        res_health = api_client.get("/api/v1/health")
        assert res_health.status_code == 503
        assert res_health.json()["error"]["code"] == "SERVICE_UNAVAILABLE"

        res_ready = api_client.get("/api/v1/health/ready")
        assert res_ready.status_code == 503
        assert res_ready.json()["error"]["code"] == "NOT_READY"

        res_live = api_client.get("/api/v1/health/live")
        assert res_live.status_code == 200


def test_sensitive_data_redaction_filter():
    """SensitiveDataFilter must mask JWTs, MongoDB URI passwords, and secret params."""
    raw = (
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature123 "
        "uri=mongodb+srv://admin:SuperSecret99@cluster0.mongodb.net/db "
        "token=reset_abc123 password=MyPassword!"
    )
    redacted = redact_sensitive_text(raw)
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted
    assert "SuperSecret99" not in redacted
    assert "reset_abc123" not in redacted
    assert "MyPassword!" not in redacted
    assert "[REDACTED_JWT]" in redacted
    assert "*****" in redacted

    record = logging.LogRecord("bizpermit.requests", logging.INFO, "", 0, raw, None, None)
    assert SensitiveDataFilter().filter(record) is True
    assert "SuperSecret99" not in record.msg


@override_settings(SLOW_REQUEST_THRESHOLD_MS=0)
def test_slow_request_logging_and_query_redaction(api_client, caplog):
    """Slow requests emit SLOW_REQUEST warning and query param tokens are redacted."""
    with caplog.at_level(logging.WARNING, logger="bizpermit.performance"):
        res = api_client.get("/api/v1/health?token=super_secret_val&page=1")
        assert res.status_code == 200

    assert any("SLOW_REQUEST" in rec.message for rec in caplog.records)
    assert all("super_secret_val" not in rec.message for rec in caplog.records)
