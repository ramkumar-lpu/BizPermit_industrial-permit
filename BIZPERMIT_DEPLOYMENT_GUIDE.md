# BizPermit — Production Deployment, Backup & Operations Guide

**Branch:** `feature/production-readiness`  

---

## 1. Pre-Deployment Checklist
- [ ] Copy `.env.example` to `.env` on the target server (never commit `.env`).
- [ ] Set `DEBUG=False`, `AUTO_SEED_DEMO_DATA=False`, `USE_MOCK_DB_IF_UNAVAILABLE=False`.
- [ ] Generate unique high-entropy `SECRET_KEY` and `JWT_SECRET_KEY` (at least 32+ random bytes).
- [ ] Set `ALLOWED_HOSTS` to your production domain(s) (e.g., `api.bizpermit.example,bizpermit.example`).
- [ ] Set `CORS_ALLOWED_ORIGINS` to your exact HTTPS origin(s).
- [ ] Set `HTTPS_ENABLED=True` when serving behind a TLS-terminating reverse proxy (enables `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and HSTS).
- [ ] Configure `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and `SUPABASE_BUCKET_NAME` for private document vault storage.
- [ ] Configure `MONGODB_URI` with authentication (or use internal Docker `mongo` on `bizpermit-network`, which is NOT exposed to the host in `docker-compose.prod.yml`).
- [ ] Set `PROD_PORT` (default `8085`, or `80` if free on host).

---

## 2. Build, Deploy & Restart Procedures

```bash
# 1. Build production images (Backend Gunicorn + WhiteNoise, Frontend Multi-Stage Nginx)
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 2. Start production stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Verify health & readiness
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -f http://localhost:${PROD_PORT:-8085}/api/v1/health/ready
```

### Graceful Restart & Stop
- Both `backend` and `mongo` specify `stop_grace_period: 30s`, and Gunicorn runs with `--graceful-timeout 30`.
```bash
# Zero-volume-loss restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend

# Stop stack cleanly (NEVER pass -v in production!)
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

---

## 3. MongoDB Backup & Restore Procedures

> [!CAUTION]
> Never run `docker compose down -v` in production. Always verify backups before performing any restore, and test restores in a separate staging volume.

### Safe Logical Backup (`mongodump`)
```bash
mkdir -p ./backups
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T mongo \
  mongodump --db bizpermit_db --archive --gzip > "./backups/bizpermit_db_$(date +%Y%m%d_%H%M%S).archive.gz"
```

### Safe Restore (`mongorestore` to Staging / Target)
```bash
# Inspect archive first without modifying live data:
# docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T mongo \
#   mongorestore --archive --gzip --dryRun < ./backups/bizpermit_db_YYYYMMDD_HHMMSS.archive.gz

# Restore into target database (only when intentionally recovering):
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T mongo \
  mongorestore --nsInclude="bizpermit_db.*" --archive --gzip < ./backups/bizpermit_db_YYYYMMDD_HHMMSS.archive.gz
```
