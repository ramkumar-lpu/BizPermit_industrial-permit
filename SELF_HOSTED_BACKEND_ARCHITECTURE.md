# BizPermit — Self-Hosted Supabase + Django Backend Architecture

**Branch:** `feature/minio-object-storage` (Audit & Design Only — No Code Modified)  
**Base Commit:** `ce37ec0`  
**Reference:** [Supabase Self-Hosting with Docker](https://supabase.com/docs/guides/self-hosting/docker)  
**Date:** November 25, 2026  

---

## 1. Executive Summary

This document defines the target self-hosted architecture for **BizPermit**, migrating infrastructure dependencies from external Supabase Cloud + standalone MongoDB to an integrated **Self-Hosted Supabase Docker Stack** paired with **Django REST Framework** (retaining all statutory compliance, applicability, workflow, and RBAC business logic), **React**, and **Nginx**.

> [!IMPORTANT]
> **Phase 5 Registry Blocker Verified:** Attempting `docker pull supabase/gotrue:latest` on the current host failed with:
> `Head "https://registry-1.docker.io/v2/supabase/gotrue/manifests/latest": tls: failed to verify certificate: x509: certificate signed by unknown authority`
> Official Supabase images cannot be pulled on this host until Docker Desktop trusts the network proxy's root CA certificate.

---

## 2. Final Target Architecture Diagram

```
                        +---------------------------------------+
                        |         CLIENT BROWSER (HTTPS)        |
                        +-------------------+-------------------+
                                            |
                                    Port 443 / 8085
                                            v
                        +---------------------------------------+
                        |       Nginx Reverse Proxy             |
                        |   - Serves React SPA (/app/dist)      |
                        |   - /api/v1/* -> django-backend:8000  |
                        |   - /supabase/* -> kong:8000          |
                        |     (Auth / Storage Signed / Realtime)|
                        +---------+-------------------+---------+
                                  |                   |
              +-------------------+                   +-------------------+
              v                                                           v
+---------------------------+                               +---------------------------+
|   Django REST Framework   |                               |  Supabase Gateway (Kong)  |
|   (Gunicorn, 3 workers)   |                               |  Internal Port 8000       |
|   - Business Logic & RBAC |                               +--+----+----+----+---------+
|   - KYA, Approvals, SLA   |                                  |    |    |    |
|   - Calls internal Kong / |<---------------------------------+    |    |    |
|     Postgres directly     |      JWT Verification / Admin         |    |    |
+-------------+-------------+                                       |    |    |
              |                                                     |    |    |
              |   +-------------------------------------------------+    |    |
              |   |                 |                    |               |    |
              v   v                 v                    v               v    |
+-------------------+   +-------------------+   +---------------+   +---------+------+
| Supabase Postgres |   |  Supabase Auth    |   |   Supabase    |   |   Supabase     |
| (supabase/postgres|   | (supabase/gotrue) |   |  Storage API  |   |   Realtime     |
|  PG 15/17)        |   | - Argon2/bcrypt   |   | (storage-api) |   | (Elixir WS)    |
| - auth schema     |   | - JWT HS256/RS256 |   | + imgproxy    |   | - CDC / WAL    |
| - storage schema  |   | - Password Reset  |   +-------+-------+   +----------------+
| - public/bizpermit|   +-------------------+           |
|   domain tables   |                                   v
+---------+---------+                       +-----------------------+
          ^                                 |  Named Docker Volume  |
          |                                 |  supabase_storage_data|
+---------+---------+                       |  (Private File Vault) |
|  Supavisor / Meta |                       +-----------------------+
|  & Studio (Admin  |
|  UI - Internal /  |
|  VPN Only)        |
+-------------------+
```

---

## 3. Docker Services & Responsibilities

| Service | Official Image | Role & Responsibility | Network & Exposure |
|---|---|---|---|
| **frontend** | `nginx:alpine` (multi-stage) | Serves React SPA + reverse proxies `/api/v1/` to Django and `/supabase/` (Storage signed URLs / Realtime WS) to Kong. | Public (`PROD_PORT` / `443`) |
| **backend** | `python:3.11-slim` (Gunicorn) | BizPermit Django REST Framework domain engine: KYA, approvals, compliance, grievances, schemes, RBAC, audit logging. | Internal (`8000`) |
| **db** | `supabase/postgres` | Primary relational database (`auth`, `storage`, `realtime`, `bizpermit` schemas) with WAL logical replication enabled. | Internal (`5432`, **NO host port in prod**) |
| **kong** | `kong:2.8.1` | Official Supabase API Gateway routing `/auth/v1/*`, `/storage/v1/*`, `/rest/v1/*`, `/realtime/v1/*`. | Internal (`8000`) |
| **auth** | `supabase/gotrue` | Manages user credentials, JWT issuance/refresh, password recovery emails, and `auth.users`. | Internal (`9999`) |
| **storage** | `supabase/storage-api` | Private S3-free file storage backed by `supabase_storage_data` volume and `storage.objects` in Postgres. | Internal (`5000`) |
| **imgproxy** | `darthsim/imgproxy` | Optional image preview resizing for `storage-api`. | Internal (`5001`) |
| **realtime** | `supabase/realtime` | Streams Postgres WAL changes for notifications, application status, officer assignment, and grievances over WebSockets. | Internal (`4000`) |
| **rest** | `postgrest/postgrest` | Auto-generated Postgres REST layer (disabled for direct public domain writes; restricted behind RLS + Django). | Internal (`3000`) |
| **meta** | `supabase/postgres-meta` | Schema introspection & SQL execution backend for Studio. | Internal (`8080`) |
| **studio** | `supabase/studio` | Admin database & auth inspection dashboard. | **Dev only (`3000`) / VPN-only in prod** |
| **supavisor** | `supabase/supavisor` | Postgres connection pooler for high concurrency. | Internal (`6543`) |

---

## 4. Storage, Realtime & Network Security Design

### Private File Storage Architecture
- **Buckets:** Private `bizpermit` bucket in `storage.buckets` (`public = false`).
- **Binary Storage:** Stored exclusively on Docker named volume `supabase_storage_data` (mounted into `storage-api`), NEVER as `bytea` inside Postgres tables.
- **Access Control:**
  - `DirectUploadView` & `ConfirmUploadView` validate magic bytes (`FileValidator`), SHA-256 checksums, business ownership, and prefix (`businesses/<business_id>/docs/`), calling internal `http://kong:8000/storage/v1/...` using `SUPABASE_SERVICE_ROLE_KEY`.
  - `DocumentPreviewView` / `DocumentDownloadView` generate short-lived (900s) signed URLs rewritten to the public reverse-proxy origin (`SUPABASE_PUBLIC_URL`, e.g., `https://portal.example.com/supabase/storage/v1/...`) so browsers never receive unresolvable internal Docker hostnames (`http://kong:8000`).

### Realtime Evaluation
- **Candidate Events:**
  1. `notifications` (replaces 30s polling in `NotificationBell.jsx` with WebSocket subscription filtered by `recipient_user_id`).
  2. `applications` (`status`, `assigned_officer_id` updates).
  3. `grievances` (`status`, clarification updates).
- **Guardrail:** Keep Django `WorkflowEngine.publish_event` as the single writer to `notifications` and `applications`; Supabase Realtime only broadcasts `INSERT`/`UPDATE` changes from Postgres WAL—no duplicate notification creation logic.

### Network & Security Controls
- **Zero Public DB / Storage Secrets:** `POSTGRES_PASSWORD`, `JWT_SECRET`, `ANON_KEY`, and `SERVICE_ROLE_KEY` reside only in server `.env` (never in `VITE_*` frontend env vars or Git).
- **Internal Isolation:** `db` (5432), `auth`, `storage`, `meta`, `kong` bind only to private Docker network `bizpermit-network` in production; `studio` is disabled or bound to `127.0.0.1`/VPN only.

---

## 5. Resource Requirements (Minimum Recommended)

| Environment | vCPU | RAM | Disk (Volumes) |
|---|---|---|---|
| **Development (Local Docker)** | 4 vCPU | 8 GB (6 GB Docker limit) | 20 GB |
| **Production (Single-Node VM)** | 4–8 vCPU | 16 GB | 100 GB+ SSD (`postgres_data` + `supabase_storage_data`) |
