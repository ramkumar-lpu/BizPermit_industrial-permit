# BizPermit — Self-Hosted Supabase Migration & Deployment Plan

**Branch:** `feature/minio-object-storage` (Proposal Only — Awaiting Approval)  
**Date:** November 25, 2026  

---

## 1. Incremental Migration Strategy (Data & Storage)

### Database Migration Script Design (`migrate_mongo_to_postgres.py`)
1. **Dry-Run Mode (`--dry-run`):** Reads MongoDB collections, validates schema mapping & UUIDv5 determinism, logs exact record counts (`users: 23`, `locations: 42`, `business_documents: 64`, `audit_logs: 155`, etc.) without writing to Postgres.
2. **Idempotent & Resumable:** Uses `legacy_mongo_id` unique constraints (`ON CONFLICT (legacy_mongo_id) DO NOTHING`) and checkpoints per collection so interrupted runs resume cleanly.
3. **Post-Migration Validation:** Compares source MongoDB counts vs target Postgres row counts and verifies foreign-key integrity (`businesses.owner_user_id`, `locations.business_id`, `applications.location_id`).
4. **Zero Destructive Cleanup:** Original MongoDB collections and `bizpermit_mongodb_data` volume are preserved read-only during validation.

### Storage Migration Strategy
- **Current State Inspection:** In the local workspace, `SUPABASE_URL` is unconfigured (`""`), and the 64 `business_documents` records in MongoDB reference sandbox paths (`businesses/<id>/docs/...`).
- **Migration Script (`migrate_storage_to_self_hosted.py`) When Cloud Objects Exist:**
  - Supports `--dry-run` and checkpoint file (`storage_migration_state.json`).
  - Downloads each object from source Supabase Cloud (only if `SOURCE_SUPABASE_URL` is configured & reachable), verifies `sha256_checksum` and `file_size_bytes` against `business_documents`, uploads to self-hosted `http://kong:8000/storage/v1/object/bizpermit/<path>`, verifies `HEAD` size/ETag, and updates `storage_provider = 'self_hosted_supabase'` only after verification. Never deletes source cloud objects automatically.

---

## 2. Deployment Sequence
1. **Resolve Registry TLS Blocker:** Trust the host proxy root CA certificate in Docker Desktop so `supabase/postgres`, `supabase/gotrue`, `supabase/storage-api`, `supabase/realtime`, `kong`, `postgrest`, `supabase/meta`, and `supabase/studio` pull cleanly over HTTPS.
2. **Generate Secrets:** Create `.env` from `.env.example` with generated `POSTGRES_PASSWORD`, `JWT_SECRET` (32+ chars), `ANON_KEY`, and `SERVICE_ROLE_KEY`.
3. **Bring Up Supabase Core (`db` -> `kong`, `auth`, `storage`, `realtime`, `meta`):** Verify health checks (`pg_isready`, `/auth/v1/health`).
4. **Apply Django/Postgres Schema & Run `--dry-run` Migration:** Inspect counts, then execute live copy + checksum verification.
5. **Cut Over Storage -> Database -> Auth -> Realtime** incrementally (one subsystem per milestone, keeping MongoDB fallback/read-only backup until sign-off).
6. **Enable Nginx Reverse Proxy + HTTPS (`HTTPS_ENABLED=True`).**

---

## 3. Risks & Rollback Strategy
| Risk | Mitigation & Rollback |
|---|---|
| **Docker Hub TLS proxy blocks image pulls** | Documented blocker; do not disable TLS verification. Import proxy root CA into Docker Desktop / WSL trust store. |
| **Argon2id hash incompatibility in GoTrue** | Test 1 user before cutover; keep Django password verification fallback during transition window. |
| **Data mismatch during Mongo -> Postgres copy** | Original MongoDB volume (`bizpermit_mongodb_data`) remains untouched; rollback by switching `DB_ENGINE=mongodb` env flag and restarting `backend`. |
| **Storage URL breakages in browser** | Rewrite signed URLs using `SUPABASE_PUBLIC_URL` routed via Nginx `/supabase/` so internal `kong:8000` is never exposed to browsers. |

---

## 4. Recommended Implementation Order
1. **Milestone 1:** Resolve Docker registry TLS CA & bring up self-hosted Supabase Compose stack (`db`, `kong`, `auth`, `storage`, `studio` dev-only).
2. **Milestone 2:** Migrate `SupabaseStorageService` to self-hosted `storage-api` (internal `kong:8000` + public Nginx `/supabase/` rewrite) & verify live uploads/downloads.
3. **Milestone 3:** Introduce PostgreSQL Django models + run `migrate_mongo_to_postgres.py --dry-run` & live validation.
4. **Milestone 4:** Cut over `Authentication` to GoTrue (`SupabaseJWTAuthentication`) with zero dual-login systems.
5. **Milestone 5:** Enable `Supabase Realtime` subscriptions in React (`NotificationBell.jsx`, application status) and decommission MongoDB after full sign-off.
