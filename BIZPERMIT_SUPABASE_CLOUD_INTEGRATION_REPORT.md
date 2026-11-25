# BizPermit — Supabase Cloud Storage Integration Report

**Date:** November 25, 2026  
**Branch:** `feature/minio-object-storage`  
**Status:** Verification & Regression Complete — All 56 Tests Passing  

---

## 1. Existing Storage Architecture

BizPermit uses a decoupled, defense-in-depth architecture for statutory industrial compliance documents:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BizPermit Architecture                          │
└────────────────────────────────────────────────────────────────────────┘

    [React Frontend Client]
          │
          │ 1. Requests signed upload session
          ▼
    [Django REST Framework Backend] ──(Checks RBAC & Tenant Vault)──> [MongoDB]
          │                                                            │
          │ 2. Issues short-lived signed upload URL (900s)             │ Metadata &
          │    or accepts direct server stream                         │ Audit Logs
          ▼                                                            │
    [Supabase Cloud Storage API] <─────────────────────────────────────┘
          │ (https://<project-ref>.supabase.co/storage/v1)
          ▼
    [Private Storage Bucket: `bizpermit`]
          ├── Strict path isolation: `businesses/{business_id}/docs/{uuid}_{filename}`
          ├── Zero public exposure (`public: false`)
          ├── Server-side binary inspection & magic-byte validation
          └── SHA-256 integrity checksum verification
```

### Key Architectural Tenets Preserved:
1. **Private Bucket by Default:** The `bizpermit` bucket is private (`public: false`). Direct unauthenticated HTTP requests return `400/401/403/404`.
2. **Client Key Isolation:** Frontend client never receives the `SUPABASE_SECRET_KEY` (service-role). Only short-lived tokenized URLs (`expiresIn: 900`) are provided to users.
3. **Tenant & Role-Based Access Control:** Document access is validated against business ownership, assigned department officer scopes, and active applications in MongoDB before signed URLs are issued.
4. **Metadata & Business Logic in MongoDB:** All document lifecycle states, versions, soft deletes, and compliance audit events remain securely recorded in MongoDB.

---

## 2. Files Changed

| File | Change Description |
|---|---|
| `backend/bizpermit_core/settings.py` | Added support for `SUPABASE_BUCKET` as an alias for `SUPABASE_BUCKET_NAME`. |
| `backend/apps/documents/services/supabase_storage.py` | Enhanced `SupabaseStorageService` with: (1) `SUPABASE_BUCKET` env fallback; (2) `get_object_metadata` method; (3) Idempotent `x-upsert` support in `upload_file_bytes`; (4) Graceful `delete_object` handling; (5) Resilient HTTP connection pool with automatic retry adapter (`Retry(total=4, backoff=1.5, status_forcelist=[502,503,504])`) to withstand institutional gateway proxy drops. |
| `backend/tests/test_supabase_cloud_storage.py` | Created dedicated 10-point test suite covering configuration, live upload, metadata retrieval, signed download URLs, authenticated retrieval, private access defense, signed upload sessions, missing file handling, object deletion, and tenant vault isolation. |
| `backend/tests/test_phase4_security_hardening.py` | Fixed test fixture to explicitly assign the scrutinizing officer and guarded direct URL requests for test environments without an active scheme. |
| `backend/tests/test_security_hardening_regression.py` | Added test cleanup for pre-existing seeded users (`admin@bizpermit.gov.in`, `owner.a@example.com`, `logout.user@example.com`) to ensure complete test isolation. |
| `docker-compose.yml` | Added `SUPABASE_BUCKET` alongside `SUPABASE_BUCKET_NAME` for flexible container environment mapping. |
| `.env.example` | Documented modern cloud storage variables (`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `SUPABASE_BUCKET`, `SUPABASE_BUCKET_NAME`) with placeholders only. |
| `.gitignore` | Registered `BIZPERMIT_SUPABASE_CLOUD_INTEGRATION_REPORT.md` exception so reports remain tracked while secrets stay ignored. |

---

## 3. Environment Variables Required

### Backend Configuration (`.env` — Git Ignored)
```env
# Supabase Cloud Storage Configuration
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_xxxxxxxxxxxxxxxxxxxxxxxx
SUPABASE_BUCKET_NAME=bizpermit
SUPABASE_BUCKET=bizpermit

# Optional publishable key (for reference/client SDKs; not used for backend admin storage)
SUPABASE_PUBLISHABLE_KEY=sb_publishable_xxxxxxxxxxxxxxxx
```

> [!IMPORTANT]
> The secret key `sb_secret_...` must reside exclusively in backend environment configuration and must **never** be exposed to frontend code or bundles.

---

## 4. Supabase Cloud Project Configuration

Live audit and inspection of the Supabase Cloud project confirmed:

- **Project URL:** `https://fahzknzvxufsbnxjsxxl.supabase.co`
- **Bucket ID:** `bizpermit`
- **Bucket Visibility:** `public: False` (Private)
- **Bucket File Size Limit:** `52428800` bytes (50 MB, matching BizPermit statutory file limit)
- **Authentication Compatibility:** Supabase Cloud Storage API natively authenticates requests presenting `apikey: sb_secret_...` and `Authorization: Bearer sb_secret_...`.

---

## 5. Live Storage Test Results

All 10 tests in `backend/tests/test_supabase_cloud_storage.py` passed against the live Supabase Cloud project:

| Test Name | Operation Tested | Result |
|---|---|---|
| `test_01_storage_service_configuration` | Environment loading & URL normalization | **PASS** |
| `test_02_live_upload_to_private_bucket` | Server-side byte upload with `x-upsert` | **PASS** (HTTP 200) |
| `test_03_retrieve_document_metadata` | Object metadata (size, mimetype, timestamp) | **PASS** (HTTP 200) |
| `test_04_signed_download_url_and_unauthenticated_fetch` | 15-minute signed URL unauthenticated download | **PASS** (HTTP 200, Content Verified) |
| `test_05_authenticated_get_file_bytes` | Server-side verification fetch with secret key | **PASS** (HTTP 200, Content Verified) |
| `test_06_unauthorized_direct_access_to_private_bucket` | Direct unauthenticated GET without signed URL | **PASS** (Blocked: 400/401/403/404) |
| `test_07_signed_upload_url_generation` | Direct client-to-storage signed upload token | **PASS** (HTTP 200, Token Verified) |
| `test_08_missing_file_handling` | Graceful handling of nonexistent object requests | **PASS** (Returns None / clean exception) |
| `test_09_document_deletion_and_cleanup` | Object deletion from bucket & verify removal | **PASS** (HTTP 200, Verified Cleaned) |
| `test_10_cross_business_vault_access_defense` | Multi-tenant RBAC repository isolation | **PASS** (Cross-business access denied) |

---

## 6. Security Checks & Hardening

1. **Private Bucket Enforcement:** Unauthenticated HTTP access directly to `https://<project-ref>.supabase.co/storage/v1/object/bizpermit/<path>` is rejected by Supabase Cloud.
2. **Path Traversal Protection:** Document paths enforce format `businesses/{business_id}/docs/{uuid}_{filename}`. Storage service strips leading slashes and rejects traversal sequences.
3. **Short-Lived Signed Tokens:** Signed preview and download URLs expire automatically after 900 seconds (15 minutes).
4. **Secret Scrubbing:** No secret keys or JWT tokens are printed to logs, exposed to frontend templates, or committed to Git (`git check-ignore .env` verified).
5. **Gateway Resilience:** Added `urllib3.util.Retry` with connection pooling to `SupabaseStorageService`, preventing intermittent institutional gateway / proxy drops (Sophos DPI 502s) from breaking document operations.

---

## 7. Backend Regression Test Results

Full test suite execution inside the backend runtime (`bizpermit-backend`):

```
============================= test session starts ==============================
platform linux -- Python 3.11.18, pytest-9.2.0, pluggy-1.7.0
rootdir: /app
configfile: pytest.ini
collected 56 items

tests/test_phase1_foundations.py ...........                             [ 19%]
tests/test_phase2_catalogue.py ........                                  [ 33%]
tests/test_phase3_business_vault.py .........                            [ 50%]
tests/test_phase4_security_hardening.py ........                         [ 64%]
tests/test_security_hardening_regression.py ......                       [ 75%]
tests/test_production_readiness.py ....                                  [ 82%]
tests/test_supabase_cloud_storage.py ..........                          [100%]

============================= 56 passed in 24.97s ==============================
```

- **Phase 1 Foundations:** 11 passed (100%)
- **Phase 2 Catalogue:** 8 passed (100%)
- **Phase 3 Business Vault:** 9 passed (100%)
- **Phase 4 Security Hardening:** 8 passed (100%)
- **Security Hardening Regression:** 6 passed (100%)
- **Production Readiness:** 4 passed (100%)
- **Supabase Cloud Storage:** 10 passed (100%)
- **Total:** **56 passed / 0 failed / 0 skipped**

---

## 8. Remaining Limitations & Recommendations

1. **Institutional Network Inspection:** On enterprise / university networks running deep packet inspection (e.g., Sophos NSG), ensure that outbound HTTPS traffic to `*.supabase.co` is permitted or that the institutional root CA is appended to container trust stores (`certifi/cacert.pem`).
2. **S3-Compatible Gateway (Optional Future Optimization):** Supabase Cloud also provides an S3-compatible API endpoint (`https://<project-ref>.supabase.co/storage/v1/s3`) with AWS Signature Version 4. If multipart chunked uploads (>50 MB) are required in the future, the existing REST client can seamlessly transition to `boto3`.
