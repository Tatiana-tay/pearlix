# Backend Environment And Runbook

Date: 2026-07-05

This runbook describes local backend setup and operational commands for the DentalCare backend. It is for local development and QA. It is not a production deployment guide.

## Repository Layout

```text
D:\pearlix
  backend\
  frontend\
  project_docs\
```

Backend app entry points:

- Django project: `backend/dentalcare_api`
- Manage script: `backend/manage.py`
- Local DB service: `backend/docker-compose.yml`
- Example environment: `backend/.env.example`

## Required Local Tools

- Windows PowerShell.
- Python available through `backend/.venv\Scripts\python.exe`.
- Docker Desktop with Linux engine running.
- PostgreSQL Docker container exposed on host port `5433`.

## Local Environment

Create `backend/.env` locally from `backend/.env.example`. Do not commit `backend/.env`.

Required local values:

```text
POSTGRES_DB=dentalcare
POSTGRES_USER=dentalcare
POSTGRES_PASSWORD=dentalcare
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
DJANGO_SECRET_KEY=dev-only-change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Why port `5433`: local host port `5432` may already be occupied by another PostgreSQL service. Docker Compose maps host `5433` to container `5432`.

## Install And Run

From `D:\pearlix\backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d db
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_dev_users
.\.venv\Scripts\python.exe manage.py runserver
```

Health check:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/health/"
```

Expected:

```json
{"status":"ok"}
```

## Seeded Development Users

Use these users only for local development and manual QA:

| Role | Username | Password | Notes |
| --- | --- | --- | --- |
| Admin | `admin@example.com` | `Admin123!` | Admin/staff flags set for Django admin access. |
| Staff | `staff@example.com` | `Staff123!` | Front-desk workflow user. |
| Doctor | `doctor@example.com` | `Doctor123!` | Doctor workflow user. |
| Staff | `inactive@example.com` | `Inactive123!` | Inactive user rejection test. |

The seed command is idempotent: it creates missing users and updates existing local users to the documented values.

## Validation Commands

From `D:\pearlix\backend`:

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test accounts core patients employees scheduling visits billing attachments ai_results --noinput
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Optional all-test command:

```powershell
.\.venv\Scripts\python.exe manage.py test --noinput
```

If `makemigrations --check --dry-run` creates or reports model changes during Phase 15, stop and inspect why. Phase 15 should not create migrations.

## Media Files

Local uploaded files are stored under `backend/media/`.

Rules:

- `backend/media/` must not be committed.
- Local uploaded files are development artifacts.
- Production storage, object storage, retention policy, backup policy, and signed URL policy remain future deployment decisions.

## Database Reset For Local Development

Only use reset steps for local development data. Do not apply these to shared or production data.

Typical safe reset:

```powershell
docker compose down
docker compose up -d db
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_dev_users
```

If you need to remove the local Docker volume, do that intentionally from Docker Desktop or with a reviewed Docker command. Local patient, appointment, billing, attachment, and AI metadata will be lost.

## Troubleshooting

Docker engine not running:

- Symptom: `docker compose up -d db` cannot connect to the Docker daemon.
- Fix: start Docker Desktop and confirm the Linux engine is running.

Port conflict:

- Symptom: local PostgreSQL on `5432` rejects or conflicts with the project DB.
- Fix: keep this project on `POSTGRES_PORT=5433`; do not change the container port.

Migration drift:

- Symptom: `makemigrations --check --dry-run` reports changes.
- Fix: inspect model changes and migrations before running `makemigrations`. Phase 15 expects no migrations.

Authentication failures:

- Confirm `seed_dev_users` was run.
- Confirm the request uses `Authorization: Bearer <accessToken>`.
- Confirm the user is active.

CORS during frontend integration:

- Confirm frontend dev server origin is listed in `CORS_ALLOWED_ORIGINS`.
- Current default allows `http://localhost:5173` and `http://127.0.0.1:5173`.

File upload failures:

- Confirm multipart form data is used.
- Confirm type and extension are supported.
- Confirm file size is within backend limits.

AI endpoint confusion:

- Backend v1 stores AI result metadata only.
- There are no inference, training, retry-execution, or model-loading endpoints in Phase 15.

## Git Hygiene

These files and folders must remain untracked:

- `backend/.env`
- `backend/.venv/`
- `backend/media/`
- `node_modules/`
- `frontend/node_modules/`
- `dist/`
- `test-results/`
- `__pycache__/`
- `*.pyc`
- local SQLite files

Do not commit secrets, local databases, media uploads, generated caches, or virtual environments.

## Production Notes Not Covered By Phase 15

Phase 15 does not configure:

- Production secrets.
- HTTPS.
- Deployment infrastructure.
- Production database backups.
- Email provider integration.
- Object storage.
- Observability/monitoring.
- WebSockets/live updates.
- AI inference infrastructure.

These require a separate deployment/security phase.
