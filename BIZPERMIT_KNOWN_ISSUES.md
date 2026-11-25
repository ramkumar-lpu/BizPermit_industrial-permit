# BizPermit — Known Issues & Pre-Deployment Blockers

**Branch:** `feature/e2e-integration-testing`  
**Date:** November 25, 2026  

---

## 1. Environment & Infrastructure Blockers
1. **Docker Hub TLS Proxy Certificate Error (`x509: certificate signed by unknown authority`):**
   - Prevents pulling `node:20-alpine` metadata from `auth.docker.io` / `registry-1.docker.io` on the current host network, blocking a fresh `frontend/Dockerfile` rebuild.
   - **Action Required:** Run `docker compose -f docker-compose.yml -f docker-compose.prod.yml build` in an environment with trusted Docker Hub TLS access so running containers include the `feature/security-hardening` and `feature/production-readiness` updates.
2. **Unconfigured Supabase Credentials:**
   - `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are empty in `.env`. Live cloud bucket uploads/downloads and `test_phase4_security_hardening.py::test_07` cannot run until real Supabase credentials are supplied.

## 2. Remaining Test Fixture Issues (2 Tests)
- `test_phase4_applications.py::test_08_full_officer_scrutiny_and_clarification_loop`
- `test_phase4_security_hardening.py::test_06_required_audit_history_for_every_transition`
- **Cause:** Both tests hardcode `officer_gj` after auto-assignment rather than selecting the dynamically assigned officer (`assigned_officer_id`), resulting in an intentional HTTP 403 from backend officer-scope enforcement.

## 3. Architectural / Security Backlog
- **JWT Storage:** Frontend stores tokens in `localStorage`; migrating refresh tokens to `HttpOnly` cookies is recommended for hardened production deployments.
- **Distributed Rate Limiting:** DRF `AnonRateThrottle` uses per-worker `LocMemCache`; for multi-worker Gunicorn (`--workers 3`), configure a shared cache backend when scaling horizontally.
