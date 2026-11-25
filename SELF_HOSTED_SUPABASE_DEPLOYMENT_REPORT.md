# BizPermit — Self-Hosted Supabase Deployment Report (Milestone 1)

**Branch:** `feature/minio-object-storage`  
**Date:** November 25, 2026  
**Deployment Status:** **CONFIGURED & VALIDATED — IMAGE PULL BLOCKED BY DOCKER DESKTOP TLS CA TRUST**  

---

## 1. Docker Registry TLS Blocker & Exact Remediation Procedure

### Root Cause Diagnosed
- **WSL Direct TLS (`openssl s_client`):** `auth.docker.io` (Let's Encrypt `CN=YE1` -> `Root YE` -> `ISRG Root X2` -> `ISRG Root X1`) and `registry-1.docker.io` (Amazon RSA 2048 M01 -> Amazon Root CA 1) both verify with `Verify return code: 0 (ok)` from WSL.
- **Docker Desktop Proxy (`docker info`):** Docker Desktop (v29.9.3) routes all registry traffic through `HTTP/HTTPS Proxy: http.docker.internal:3128` on the Windows host. Pulling official images (`docker pull supabase/gotrue:latest`) fails inside Docker Desktop's forwarder with:
  ```text
  Head "https://registry-1.docker.io/v2/supabase/gotrue/manifests/latest": tls: failed to verify certificate: x509: certificate signed by unknown authority
  ```
- **Why Manual User Action Is Required:** Disabling TLS verification or configuring insecure registries is prohibited. The Windows host / Docker Desktop must trust the missing Root CA certificate (`ISRG Root X2` / `Root YE` or any corporate/antivirus TLS proxy CA).

### Required Windows / Docker Desktop CA Trust Procedure
1. **Export the active proxy/root CA certificate** (`.cer` / `.crt`, Base-64 encoded X.509) from your Windows network/antivirus proxy or from `auth.docker.io` (`ISRG Root X1` / `ISRG Root X2`).
2. **Install into Windows Trusted Root Store:**
   - Press `Win + R`, run `certlm.msc` (Local Computer Certificates).
   - Expand **Trusted Root Certification Authorities -> Certificates**.
   - Right-click -> **All Tasks -> Import...** and import the Root CA certificate.
3. **Also optionally place PEM CA cert for Docker Engine:**
   - Save as `%USERPROFILE%\.docker\certs.d\registry-1.docker.io\ca.crt` and `%USERPROFILE%\.docker\certs.d\auth.docker.io\ca.crt`.
4. **Restart Docker Desktop** completely (Quit from system tray -> relaunch).

---

## 2. Official Pinned Images & Services Configured (`docker-compose.supabase.yml`)

| Service | Pinned Official Image | Host Port Exposure | Health Check | Named Volume |
|---|---|---|---|---|
| `supabase-db` | `supabase/postgres:15.8.1.044` | **None (Internal `5432`)** | `pg_isready -U postgres -h localhost` | `supabase_postgres_data` |
| `supabase-auth` | `supabase/gotrue:v2.167.0` | **None (Internal `9999`)** | `wget --spider http://127.0.0.1:9999/health` | — |
| `supabase-rest` | `postgrest/postgrest:v12.2.3` | **None (Internal `3000`)** | — | — |
| `supabase-storage` | `supabase/storage-api:v1.14.5` | **None (Internal `5000`)** | `wget --spider http://127.0.0.1:5000/status` | `supabase_storage_data` |
| `supabase-meta` | `supabase/postgres-meta:v0.84.2` | **None (Internal `8080`)** | — | — |
| `supabase-kong` | `kong:2.8.1` | `127.0.0.1:8100->8000` | `kong health` | — |
| `supabase-studio` | `supabase/studio:20250113-83c9420` | `127.0.0.1:3001->3000` (`dev` profile only) | — | — |

---

## 3. Configuration & Security Validation Results

- **Compose Validation:**
  - `docker compose -f docker-compose.supabase.yml config --quiet` -> **PASS (`SUPABASE_COMPOSE_PROD_STYLE_VALID`)**
  - `docker compose -f docker-compose.supabase.yml --profile dev config --quiet` -> **PASS (`SUPABASE_COMPOSE_DEV_STYLE_VALID`)**
- **Secrets & Git Safety:**
  - Generated high-entropy `SUPABASE_POSTGRES_PASSWORD`, `SUPABASE_JWT_SECRET`, and signed HS256 `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` into `.env`.
  - `git check-ignore .env` confirmed `.env` is strictly ignored; `.env.example` updated with placeholders only.
- **BizPermit Operational Isolation:** Existing BizPermit containers (`bizpermit-frontend-prod`, `bizpermit-backend`, `bizpermit-mongo`) and `bizpermit_mongodb_data` remain untouched and operational.

---

## 4. Storage, Persistence & Runtime Verification Status

- **Prepared Validation Script:** [infra/supabase/validate_storage.py](file:///mnt/c/Users/ramku/Downloads/Industrial_compliance-and-document_aprroval-main/Industrial_compliance-and-document_aprroval-main/infra/supabase/validate_storage.py) (tests Auth health, Storage health, private bucket creation, PDF upload, unauthenticated access rejection, and signed download).
- **Live Execution Status:** **PENDING / BLOCKED** — Containers could not be started yet because `docker pull` is blocked by the Docker Desktop TLS CA error above. No live storage upload/download or container restart persistence claims are made.
- **Estimated Resource Consumption (when running):** ~2.5–3.5 GB RAM idle across the 7 Supabase containers (`postgres`, `gotrue`, `postgrest`, `storage-api`, `meta`, `kong`, `studio`).

---

## 5. Commands to Run Once CA Trust Is Installed
```bash
# 1. Start self-hosted Supabase (dev profile includes Studio on 127.0.0.1:3001)
docker compose -f docker-compose.supabase.yml --profile dev up -d

# 2. Verify all containers pass health checks
docker compose -f docker-compose.supabase.yml --profile dev ps

# 3. Run storage & health validation script (loads keys from .env)
set -a && source .env && set +a
python3 infra/supabase/validate_storage.py

# 4. Verify persistence across restart (NEVER pass -v)
docker compose -f docker-compose.supabase.yml restart supabase-storage supabase-db
```
