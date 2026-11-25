# BizPermit — Monitoring, Logging & Observability Guide

**Branch:** `feature/production-readiness`  

---

## 1. Health & Probe Endpoints

| Endpoint | Purpose | Healthy Status | Unhealthy Status |
|---|---|---|---|
| `GET /api/v1/health` | Full gateway summary (`environment`, `database_health`, `storage_health`) | `200 OK` | `503 SERVICE_UNAVAILABLE` (if MongoDB disconnected) |
| `GET /api/v1/health/live` | Liveness probe (Django/Gunicorn worker responsiveness) | `200 OK` | N/A (process down) |
| `GET /api/v1/health/ready` | Readiness probe (verifies live MongoDB `ping`) | `200 OK` | `503 NOT_READY` (if MongoDB disconnected) |

- Optional external services (Supabase Storage) report `"status": "configured"` or `"unconfigured_fallback"` with `"optional_for_core_api": true` and never mark the core API down.
- No credentials, connection strings, or stack traces are exposed in any probe response.

---

## 2. Structured Logging & Correlation IDs

Every HTTP request passes through `apps.common.middleware.RequestObservabilityMiddleware`:
- **Correlation ID:** Uses incoming `X-Request-ID` (if safe alphanumeric `6–64` chars) or generates `req_<12-hex>`; returned in `X-Request-ID` header and JSON `meta.request_id`.
- **Latency Header:** Returned in `X-Response-Time-Ms`.
- **Log Format (`bizpermit.requests`):**
  ```text
  [2026-11-25 05:55:13,503] INFO bizpermit.requests: request_id=req_c2a759bf0382 method=GET path=/api/v1/admin/audit-logs status=200 duration_ms=2.21 user=6b067841e85db361413243f3
  ```
- **Log Levels:** `INFO` for `2xx/3xx` (excluding `/api/v1/health/live` noise), `WARNING` for `4xx`, `ERROR` for `5xx` and unhandled exceptions (`bizpermit.errors`).

### Sensitive Data Redaction (`SensitiveDataFilter`)
All `bizpermit.*` and `django.request` logs pass through `SensitiveDataFilter`:
- Bearer JWTs -> `Bearer [REDACTED_JWT]`
- MongoDB URI passwords (`://user:pass@`) -> `://user:*****@`
- Query parameters & key-value pairs (`token`, `password`, `secret`, `key`, `access_token`, `refresh_token`) -> `[REDACTED]`

---

## 3. Slow-Request Performance Monitoring
- Controlled by `SLOW_REQUEST_THRESHOLD_MS` (default `500` ms).
- Requests exceeding the threshold emit:
  ```text
  WARNING bizpermit.performance: SLOW_REQUEST request_id=... method=... path=... duration_ms=... threshold_ms=500
  ```

---

## 4. Inspecting Logs in Docker
```bash
# Live backend request, performance & error logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend

# Filter slow requests or errors
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend | grep -E "SLOW_REQUEST|ERROR"
```
