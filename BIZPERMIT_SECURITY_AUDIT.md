# BizPermit — Security Audit

**Branch:** `feature/security-hardening`  
**Base Commit:** `5606478` (`feature/performance-architecture`)  
**Date:** November 25, 2026  

---

## 1. Audit Scope & Methodology
Audited all security domains across BizPermit:
- **Authentication & Session Security:** JWT (`jwt_service.py`), DRF auth (`authentication.py`), password hashing (`password.py`), login/register/reset (`views.py`, `serializers.py`).
- **Authorization & RBAC / IDOR:** `permissions.py`, `businesses/views.py`, `documents/views.py`, `grievances/views.py`, `administration/views.py`, `compliance/views.py`.
- **Document & File Security:** `FileValidator` (`file_validator.py`), `SupabaseStorageService` (`supabase_storage.py`), `UploadSessionView`, `ConfirmUploadView`.
- **API & MongoDB Security:** `$regex` query construction across repositories/views, rate throttling, exception handler (`exceptions.py`), CORS/headers (`settings.py`, `frontend/nginx.conf`).
- **Validation of `5606478` Performance Optimizations:** Verified `BaseRepository.find_by_ids`, batch lookups in `administration`/`compliance`, `_validate_vault_document_ownership`, `ensure_all_indexes` guard, and React context memoization introduced zero authorization bypasses or regressions.

---

## 2. Confirmed Vulnerabilities by Severity

| ID | Severity | Area | Finding | Affected File(s) & Endpoint(s) |
|---|---|---|---|---|
| **SEC-01** | **CRITICAL** | Auth / Backdoor | Hardcoded fallback demo passwords (`"password123"`, `"password123!"`, `"securepass123!"`) bypassed Argon2id verification for `admin@bizpermit.gov.in`, officers, and demo owner even when `DEBUG=False`. | `backend/apps/authentication/serializers.py` (`LoginSerializer.validate`) — `POST /api/v1/auth/login` |
| **SEC-02** | **CRITICAL** | Auth / Seeding | `LoginSerializer.validate` auto-triggered demo & catalog seeding on empty DB or demo email login regardless of `AUTO_SEED_DEMO_DATA=False`. | `backend/apps/authentication/serializers.py` (`LoginSerializer.validate`) — `POST /api/v1/auth/login` |
| **SEC-03** | **HIGH** | Document Vault / IDOR | `ConfirmUploadView` accepted arbitrary `storage_object_path` from the request body without verifying ownership prefix (`businesses/<business_id>/docs/`) or blocking `..` path traversal, allowing cross-tenant file attachment/exfiltration. | `backend/apps/documents/views.py` (`ConfirmUploadView.post`) — `POST /api/v1/documents/confirm-upload` |
| **SEC-04** | **HIGH** | Auth / Enumeration | `ForgotPasswordView` returned `"reset_sent": True/False` depending on account existence, and `ForgotPasswordSerializer.save()` returned `reset_url` containing the secret token. | `backend/apps/authentication/views.py` & `serializers.py` — `POST /api/v1/auth/forgot-password` |
| **SEC-05** | **HIGH** | Rate Limiting | `AuthBurstRateThrottle` overrode `auth_burst` (`10/min`) with `60/minute`, and `TokenRefreshView` had no throttle class. | `backend/apps/authentication/views.py`, `settings.py` — `/api/v1/auth/*` |
| **SEC-06** | **HIGH** | Injection / ReDoS | 35+ MongoDB `$regex` search queries across 9 modules interpolated raw user input without `re.escape()` or length bounds, risking ReDoS and regex operator injection. | `administration`, `applications`, `approvals`, `compliance`, `departments`, `documents`, `grievances`, `schemes` |
| **SEC-07** | **MEDIUM** | Headers & Cookies | `frontend/nginx.conf` lacked `server_tokens off`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and `client_max_body_size`; `settings.py` lacked explicit HTTPOnly/SameSite/HTTPS cookie flags. | `frontend/nginx.conf`, `backend/bizpermit_core/settings.py` |

---

## 3. Security Controls Already Verified Strong
- **Password Hashing:** Argon2id (`time_cost=3, memory_cost=65536, parallelism=4`) in `password.py`.
- **JWT Lifecycle:** HS256 with `exp`, `iat`, `sub`, `jti` required claims, short-lived access tokens (15m), single-use rotating refresh tokens, and MongoDB `revoked_tokens` TTL blacklist.
- **File Content Validation:** Magic-byte signature verification (PDF/PNG/JPEG), dangerous extension blocklist, SHA-256 checksums, and filename sanitization in `FileValidator`.
- **Error Handling:** Centralized `custom_exception_handler` masks unhandled 500 tracebacks in API JSON responses.
