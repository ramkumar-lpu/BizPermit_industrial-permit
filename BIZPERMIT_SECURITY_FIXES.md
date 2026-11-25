# BizPermit — Security Fixes Implemented

**Branch:** `feature/security-hardening`  
**Date:** November 25, 2026  

---

## 1. Removed Hardcoded Demo Password Backdoor & Unconditional Login Seeding (SEC-01, SEC-02)
- **File:** `backend/apps/authentication/serializers.py` (`LoginSerializer.validate`)
- **Fix:**
  - Removed the hardcoded fallback password check (`"password123"`, `"password123!"`, `"securepass123!"`) so all accounts strictly require valid Argon2id verification via `verify_password()`.
  - Gated auto-seeding in `LoginSerializer` behind `getattr(settings, 'AUTO_SEED_DEMO_DATA', False)` so production logins never auto-create demo accounts.

## 2. Fixed Cross-Tenant `storage_object_path` IDOR & Path Traversal (SEC-03)
- **File:** `backend/apps/documents/views.py` (`ConfirmUploadView.post`)
- **Fix:** Enforced strict validation that `storage_object_path` has no `..` or `\` traversal sequences and strictly begins with `f"businesses/{business_id}/docs/"` (with non-empty filename), raising `PermissionDeniedException` (HTTP 403) otherwise.

## 3. Eliminated Password-Reset Email Enumeration & Token URL Return (SEC-04)
- **Files:** `backend/apps/authentication/views.py` (`ForgotPasswordView`), `backend/apps/authentication/serializers.py` (`ForgotPasswordSerializer`)
- **Fix:**
  - Removed `"reset_sent"` boolean from `ForgotPasswordView` response and audit delta; endpoint now returns uniform `{"reset_requested": True, "email": ...}` regardless of whether the email exists.
  - Removed `"reset_url"` from `ForgotPasswordSerializer.save()` return value.

## 4. Enforced Strict Auth Rate Limiting (`auth_burst`) & Refresh Throttling (SEC-05)
- **Files:** `backend/apps/authentication/views.py`, `backend/bizpermit_core/settings.py`
- **Fix:**
  - Changed `AuthBurstRateThrottle` from `rate = '60/minute'` to `scope = 'auth_burst'` (enforcing `10/minute` in runtime/production via `DEFAULT_THROTTLE_RATES`, while permitting `1000/minute` during `pytest` runs).
  - Applied `throttle_classes = [AuthBurstRateThrottle]` to `TokenRefreshView`.

## 5. Prevented MongoDB `$regex` Injection & ReDoS Across All Search Endpoints (SEC-06)
- **Files:** `backend/apps/common/base_repository.py` (`BaseRepository.safe_regex`) + 11 repository/view files (`administration/views.py`, `applications/repository.py`, `approvals/repository.py`, `compliance/repository.py`, `departments/repository.py`, `documents/repository.py`, `documents/views.py`, `grievances/repository.py`, `grievances/views.py`, `schemes/repository.py`, `schemes/review_repository.py`, `schemes/views.py`).
- **Fix:** Added `BaseRepository.safe_regex(search_query, max_len=100)` using `re.escape()` and length bounding, and replaced raw `$regex` interpolation across all search queries.

## 6. Hardened Django Security Settings & Nginx Headers (SEC-07)
- **Files:** `backend/bizpermit_core/settings.py`, `frontend/nginx.conf`
- **Fix:**
  - Enabled `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`, `SameSite='Lax'`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS='DENY'`, `SECURE_REFERRER_POLICY='same-origin'`, and conditional `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` / HSTS when `HTTPS_ENABLED=True` and `DEBUG=False`.
  - Added `server_tokens off;`, `client_max_body_size 55M;`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` in `frontend/nginx.conf`.
