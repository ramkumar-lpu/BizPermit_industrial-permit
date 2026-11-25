# BizPermit — Authentication Migration Plan (Django JWT -> Self-Hosted Supabase Auth)

**Branch:** `feature/minio-object-storage` (Design Only — No Code Modified)  
**Date:** November 25, 2026  

---

## 1. Current Authentication Architecture
- **Password Hashing:** Argon2id (`argon2-cffi`, `time_cost=3, memory_cost=65536, parallelism=4`) in `backend/apps/authentication/password.py`.
- **Token Issuance:** Custom HS256 JWTs (`access` 15m, `refresh` 7d) signed with `JWT_SECRET_KEY` in `jwt_service.py`.
- **Session Revocation:** MongoDB `revoked_tokens` collection with TTL index on `expires_at`.
- **DRF Principal & RBAC:** `MongoJWTAuthentication` loads the user document and constructs `MongoUserPrincipal` (`role`: `BUSINESS_OWNER`, `DEPARTMENT_OFFICER`, `SUPER_ADMIN`; `officer_profile` scoping).

---

## 2. Target Single-Auth Architecture (Zero Dual-Login Systems)
1. **Single Identity Provider:** Self-hosted **Supabase Auth (`supabase/gotrue`)** becomes the sole issuer of access/refresh JWTs and handler of password recovery.
2. **Django Token Verification:** `SupabaseJWTAuthentication` replaces `MongoJWTAuthentication` in DRF:
   - Verifies the Bearer JWT signature using `SUPABASE_JWT_SECRET` (or GoTrue JWKS endpoint).
   - Extracts `sub` (UUID), looks up `public.user_profiles` (cached/indexed by `id`), checks `is_active` and `DEPARTMENT_OFFICER` verification status, and constructs `BizPermitUserPrincipal` preserving all existing DRF permission classes (`IsBusinessOwner`, `IsDepartmentOfficer`, `IsSuperAdmin`, `IsOwnerOrOfficer`).
3. **API Contract Preservation:** Existing endpoints (`/api/v1/auth/login`, `/register`, `/refresh`, `/logout`, `/forgot-password`, `/reset-password`, `/me`) remain intact as thin proxies to internal GoTrue (`http://kong:8000/auth/v1/...`), or frontend calls GoTrue directly once cut over, ensuring **zero breaking changes** for React or existing tests.

---

## 3. Existing User & Password Migration Strategy
- **User Records (23 existing MongoDB users):**
  - Generate deterministic UUIDv5 `id` from `user._id`.
  - Insert into `auth.users` via Supabase Admin API (`POST /auth/v1/admin/users`) or controlled SQL migration into `auth.users` + `auth.identities` + `public.user_profiles`.
- **Password Hash Compatibility:**
  - GoTrue natively supports `$2a$`/`$2b$` (bcrypt) and `$argon2id$` hashes (when `GOTRUE_PASSWORD_REQUIRED_CHARACTERS` / argon2 support is enabled in GoTrue).
  - **Verification Gate:** Before cutover, test 1 migrated Argon2id hash against `supabase/gotrue` `/token?grant_type=password`. If a legacy hash format mismatch occurs, implement a transparent **lazy re-hash on next login** via Django fallback verification during a 30-day transition window, or trigger mandatory password reset for unverified accounts.
- **Role & Officer Scope Storage:** Store authoritative `role`, `is_active`, `is_verified`, and `officer_profile` in `public.user_profiles` (NOT mutable user-editable `user_metadata`), enforced by Django RBAC so users can never escalate roles via GoTrue `PATCH /user`.
