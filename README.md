# BizPermit

BizPermit is an industrial compliance and statutory approval portal. It supports business and facility onboarding, permit applications, officer review, document handling, compliance tracking, schemes, grievances, and administrative oversight.

## Architecture

- **Frontend:** React 18 and Vite.
- **API:** Django 5.1+ and Django REST Framework.
- **Application data:** MongoDB 7 through PyMongo. Django's SQL database configuration is for framework compatibility; the business repositories use MongoDB.
- **Document storage:** Optional Supabase Storage integration for cloud-backed documents.
- **Containers:** Docker Compose runs MongoDB, the Django API, and the Vite development server. The production override runs Gunicorn and serves the frontend through Nginx.

## Run locally with Docker

Prerequisites: Docker Desktop (or Docker Engine) with Docker Compose v2.

From the repository root:

```powershell
docker compose up --build -d
docker compose ps
```

The development services are available at:

- Frontend: <http://localhost:5173>
- API: <http://localhost:8000>
- MongoDB: `localhost:27017`

The Compose configuration has development defaults. For cloud document storage or a deployment, configure the relevant values from `.env.example` in a local `.env` file. Never commit `.env` or use development defaults in production.

Stop the development services while preserving MongoDB data:

```powershell
docker compose down
```

To run the production Compose configuration locally:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

The production frontend is served at `http://localhost:8085` by default; `PROD_PORT` can override the host port. Configure strong secrets, allowed hosts, CORS origins, database access, and TLS termination before deployment.

## Run checks without Docker

With Node.js 20+ and frontend dependencies installed, run these commands from `frontend/`:

```powershell
npm test
npm run build
```

With Python 3.11+ and backend requirements installed, run this command from `backend/`:

The backend suite includes live Supabase Storage integration tests. They require valid storage credentials and network access; without them, those cloud-specific cases fail.

```powershell
python -m pytest
```

## Documentation

- [Docker development and production setup](docs/development/docker.md)
- [Application workflow map](docs/architecture/workflows.md)
- [Deployment and MongoDB operations](docs/operations/deployment.md)
- [Health checks, logging, and monitoring](docs/operations/monitoring.md)

## Configuration and security

Use `.env.example` as a reference for supported environment variables. Keep real credentials in an untracked `.env` file or your deployment secret manager. Do not expose Supabase secret keys or production database credentials to the frontend.
