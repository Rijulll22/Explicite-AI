# Explicite AI — Backend

FastAPI + PostgreSQL backend for the Explicite AI explainable code-review platform.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Runtime |
| Docker Desktop | Any recent | Local PostgreSQL via Docker Compose |
| Git | Any | Version control |

## Quick start

### 1. Install Docker Desktop

Download and start [Docker Desktop](https://www.docker.com/products/docker-desktop/).
Confirm it is running before proceeding:

```
docker info
```

### 2. Clone and enter the backend directory

```
cd "USABILITY PROJECT/backend"
```

### 3. Create a virtual environment and install dependencies

```
py -m venv venv
.\venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and fill in values:

```
copy .env.example .env
```

Generate a secure `JWT_SECRET_KEY`:

```
py -c "import secrets; print(secrets.token_hex(64))"
```

Paste the output into `JWT_SECRET_KEY` in `.env`.
Set `POSTGRES_PASSWORD` and `DATABASE_URL` to match.

`.env` is listed in `.gitignore` — **never commit it**.

### 5. Start PostgreSQL

```
docker compose up -d
```

Wait for the health check to pass:

```
docker compose ps
```

### 6. Create the test database

```
docker exec -it backend-db-1 psql -U explicite -c "CREATE DATABASE test_explicite_ai;"
```

Replace `backend-db-1` with the actual container name shown by `docker compose ps`.

### 7. Run database migrations

```
.\venv\Scripts\alembic upgrade head
```

### 8. Seed the database

```
.\venv\Scripts\python seed.py
```

This inserts the exact mock data from `frontend/src/data.ts`:
- 1 user: `jane.doe@university.ac.uk` / `password`
- 4 projects with analysis jobs
- 8 issues for Student Management System
- 7 learning resources + 3 learning paths

Safe to re-run; uses `INSERT ... ON CONFLICT DO NOTHING`.

### 9. Start the API server

```
.\venv\Scripts\uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000  
Swagger UI: http://localhost:8000/docs  
Health check: http://localhost:8000/health

## Running tests

Tests use a **separate PostgreSQL database** (`test_explicite_ai`).
Create it first (see Step 6 above), then:

```
.\venv\Scripts\pytest -v
```

The test suite creates tables before running and truncates them after each test.

## Generating a new migration

After changing a model:

```
.\venv\Scripts\alembic revision --autogenerate -m "describe your change"
.\venv\Scripts\alembic upgrade head
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | asyncpg DSN for the main database |
| `TEST_DATABASE_URL` | No | asyncpg DSN for the test database (defaults to DATABASE_URL with `/test_explicite_ai`) |
| `JWT_SECRET_KEY` | Yes | 64-byte hex secret for signing JWTs |
| `JWT_ALGORITHM` | No | Default: `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | Default: `60` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins. Default: `http://localhost:8443` |
| `POSTGRES_USER` | Yes (Docker) | Used by docker-compose.yml |
| `POSTGRES_PASSWORD` | Yes (Docker) | Used by docker-compose.yml |
| `POSTGRES_DB` | Yes (Docker) | Used by docker-compose.yml |
| `LLM_PROVIDER` | No | `none` (deferred). Future: `anthropic`, `ollama` |

## API endpoints (Milestone 1)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | — | Liveness check |
| `POST` | `/api/v1/auth/login` | — | Email/password login → JWT |
| `GET` | `/api/v1/auth/me` | Bearer | Current user profile |
| `GET` | `/api/v1/projects` | Bearer | Projects the user is a member of |
| `GET` | `/api/v1/projects/{id}/dashboard` | Bearer | Dashboard metrics + priority issues |
| `GET` | `/api/v1/projects/{id}/issues` | Bearer | Findings with filters |
| `GET` | `/api/v1/projects/{id}/issues/{issue_id}` | Bearer | Finding detail |

### Issue filters (`GET /api/v1/projects/{id}/issues`)

| Parameter | Values |
|-----------|--------|
| `severity` | `Critical`, `High`, `Medium`, `Low` |
| `type` | `Vulnerability`, `Bug`, `Code Smell`, `Security Hotspot` |
| `status` | `Open`, `In Review`, `Resolved` |
| `q` | Substring match in title or file path (case-insensitive) |
| `skip` | Offset (default 0) |
| `limit` | Page size (default 50, max 100) |

## Database schema

```
users
  id, email, password_hash, full_name, system_role, department,
  experience_level, is_email_verified, is_active, created_at, updated_at

projects
  id, name, description, source_type, default_branch, owner_id,
  archived_at, created_at, updated_at

project_memberships
  project_id, user_id, role (owner|developer|viewer), created_at

analysis_jobs
  id, project_id, status, source_revision, source_branch, engine_name,
  engine_version, quality_gate_passed, bugs_count, vulnerabilities_count,
  code_smells_count, security_hotspots_count, coverage_pct, duplications_pct,
  technical_debt_minutes, failure_reason, scoring_model_version,
  created_at, started_at, completed_at, failed_at

findings
  id, analysis_job_id, project_id, engine_severity, risk_level, risk_score,
  risk_score_version, issue_type, title, rule_key, file_path, line_number,
  description, ai_explanation, status, cwe_id, owasp_category, cvss_score,
  created_at, updated_at

learning_resources
  id, title, resource_type, duration_minutes, description, tag,
  is_curated, related_issue_type, related_rule_key, created_at

learning_paths
  id, name, description, module_count, created_at

user_learning_progress
  id, user_id, path_id, resource_id, progress_pct, completed_at,
  created_at, updated_at
```

## Security notes

- Password hashes use bcrypt (work factor 12). Never returned in API responses.
- JWTs are signed with HS256 using a per-deployment secret from the environment.
- All project endpoints enforce membership server-side. Changing a project ID in the
  URL without membership returns 403, not the project data.
- Findings in the wrong project return 404 (not 403) to avoid leaking existence.
- Inactive users cannot authenticate even with correct credentials.
- Timing-safe dummy hash comparison prevents user-enumeration via login timing.

## Project isolation guarantee

Every protected route calls `get_project_membership()` in `app/api/deps.py`.
This function:
1. Verifies the project exists and is not archived.
2. Checks the authenticated user has a `ProjectMembership` row for that project.
3. Verifies the membership role meets the minimum required level.
System administrators bypass membership checks and have owner-level access.

## Frontend integration notes

The frontend (`../frontend`) currently uses hardcoded data from `src/data.ts`.
To wire it up to this backend:
1. Start this API on port 8000.
2. In the frontend, replace direct references to `data.ts` with `fetch` calls to the
   API endpoints listed above.
3. Pass the JWT from the login response in the `Authorization: Bearer <token>` header.
4. The `FindingSummary` schema field names match the `Issue` TypeScript interface
   in `data.ts` exactly (`severity`, `type`, `title`, `rule`, `file`, `line`, `risk`, `status`).
