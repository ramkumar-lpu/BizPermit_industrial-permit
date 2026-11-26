# BizPermit — Docker Development and Production Setup

This document describes how to build, run, and manage the complete **BizPermit (Industrial Compliance & Document Approval Platform)** using Docker and Docker Compose without requiring Python, Node.js, npm, or MongoDB installed on the host machine.

---

## Architecture Overview

BizPermit consists of three containerized services running on an isolated Docker network (`bizpermit-network`):

```
+-------------------------------------------------------------------------------+
|                               HOST MACHINE                                    |
|                                                                               |
|   Development:                                                                |
|     - Port 5173  -> Frontend (Vite HMR Development Server)                   |
|     - Port 8000  -> Backend (Django Development Server)                      |
|     - Port 27017 -> MongoDB 7.0 Community Engine                             |
|                                                                               |
|   Production:                                                                 |
|     - Port 8085 (Configurable via PROD_PORT) -> Frontend (Nginx Reverse Proxy)|
|     - Backend: Port 8000 (Internal Only — Gunicorn 3 Workers)                 |
|     - Database: Port 27017 (Internal Only — MongoDB 7.0)                      |
+-------------------------------------------------------------------------------+
```

### Persistence Architecture
- **Application Persistence:** MongoDB 7.0 via PyMongo (`bizpermit_db`). All domain entities (users, enterprises, facilities, approvals, obligations, grievances, schemes, audit trails) persist in the Docker named volume `bizpermit_mongodb_data`.
- **Framework SQL:** Django uses an internal in-memory SQLite database (`:memory:`) purely for session/framework compatibility; all business logic persists to MongoDB.
- **Document Storage:** Supabase Storage REST API with local mock fallbacks when offline or unconfigured.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS) or Docker Engine + Docker Compose v2 (Linux / WSL2).
- Git.

---

## 1. Quick Start: Development Environment

The development stack provides hot-reloading for React (Vite) and auto-reload for Django via bind-mounts.

### Step 1: Prepare Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### Step 2: Build & Start Development Services
```bash
# Build images
docker compose build

# Start services in background
docker compose up -d
```

### Step 3: Verify Status & Health
```bash
docker compose ps
```
All containers (`bizpermit-mongo`, `bizpermit-backend`, `bizpermit-frontend`) should display `Up (healthy)`.

### Development Access Points
- **Frontend (Vite UI):** [http://localhost:5173](http://localhost:5173)
- **Backend API Gateway:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **MongoDB Host Port:** `localhost:27017`

Development demo data may be seeded when `AUTO_SEED_DEMO_DATA` is enabled. Do not use demo accounts or development secrets outside a local development environment.

---

## 2. Production Environment

The production stack uses:
- **Frontend:** Multi-stage Nginx container serving optimized static assets with SPA routing fallback (`try_files $uri $uri/ /index.html`) and `/api/` reverse proxy.
- **Backend:** Gunicorn WSGI server running 3 workers with `DEBUG=False`.
- **Database:** MongoDB 7.0 on internal Docker network (NOT published to host).
- **Security:** Demo data auto-seeding is strictly disabled (`AUTO_SEED_DEMO_DATA=False`).

### Step 1: Configure Production Port (Optional)
In `.env` or as an environment variable, configure `PROD_PORT` (default is `8085` to avoid Windows host port 80/8080 conflicts):
```env
PROD_PORT=8085
```

### Step 2: Build & Start Production Services
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

### Step 3: Verify Production Status
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Output:
```
NAME                      COMMAND                  STATUS                    PORTS
bizpermit-backend         "gunicorn bizpermit_…"   Up (healthy)              8000/tcp (internal)
bizpermit-frontend-prod   "nginx -g 'daemon of…"   Up (healthy)              0.0.0.0:8085->80/tcp
bizpermit-mongo           "docker-entrypoint.s…"   Up (healthy)              27017/tcp (internal)
```

### Production Access Points
- **Unified Portal (Nginx):** [http://localhost:8085](http://localhost:8085)
- **Proxied API Health Check:** [http://localhost:8085/api/v1/health](http://localhost:8085/api/v1/health)

---

## 3. Common Management Commands

### Viewing Logs
```bash
# All development logs
docker compose logs -f

# Specific production service logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f frontend
```

### Running Tests Inside Containers
```bash
# Execute backend test suite
docker compose exec backend pytest

# Execute tests in production container
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend pytest
```

### Stopping Services
```bash
# Stop development services (preserves database data)
docker compose down

# Stop production services (preserves database data)
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

> [!WARNING]
> Never run `docker compose down -v` unless you explicitly intend to permanently delete the persistent MongoDB database volume.

---

## 4. Troubleshooting & FAQ

### Port 80 or 8080 Conflict on Windows
On Windows machines, port 80 is often claimed by the World Wide Web Publishing Service (`http.sys`), and port 8080 may be in use by other local developer tools (e.g. Java).
- **Solution:** Change `PROD_PORT` in `.env` to any free port (e.g., `PROD_PORT=8085` or `PROD_PORT=8081`). The internal container port remains 80.

### Idempotent Database Restarts
On the initial run in development, `apps.database.apps.DatabaseConfig.ready()` checks if `admin@bizpermit.gov.in` exists. If missing, it populates demo data. On subsequent restarts, it detects the existing user and skips seeding without modifying existing records. In production, seeding is completely turned off via `AUTO_SEED_DEMO_DATA=False`.
