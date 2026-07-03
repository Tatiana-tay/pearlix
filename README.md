# Pearlix / DentalCare

## Structure

- `frontend/` React + Vite app
- `backend/` Django + DRF API
- `project_docs/` planning, handoff, rules, and phase tracker

## Frontend

```bash
cd frontend
npm install
npm run typecheck
npm run build
```

## Backend

The local Docker database maps host port `5433` to PostgreSQL container port `5432`.

```bash
cd backend
docker compose up -d db
python manage.py migrate
python manage.py test
python manage.py runserver
```
