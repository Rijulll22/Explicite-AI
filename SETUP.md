# Explicite AI — Setup Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.14+ | Tested on 3.14.3 |
| Node.js | 22+ | Via mise/nvm |
| pnpm | 9+ | `npm install -g pnpm` |
| PostgreSQL | 16 | Docker recommended |
| Semgrep | 1.181.0 | `pip install semgrep` |
| Docker (optional) | 27+ | For the DB container |

---

## 1. Start PostgreSQL

Using Docker:

```sh
docker run -d \
  --name explicite-db \
  -e POSTGRES_USER=explicite \
  -e POSTGRES_PASSWORD=change_this_in_production \
  -e POSTGRES_DB=explicite_ai \
  -p 5434:5432 \
  postgres:16
```

Create the test database:

```sh
docker exec -it explicite-db psql -U explicite -c "CREATE DATABASE test_explicite_ai;"
```

---

## 2. Backend

```sh
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt
pip install semgrep
```

### Configure environment

```sh
cp .env.example .env
```

Edit `.env`:
- Set `DATABASE_URL` and `TEST_DATABASE_URL` with your DB credentials and port (5434 if using the Docker command above).
- Generate a `JWT_SECRET_KEY`:
  ```sh
  python -c "import secrets; print(secrets.token_hex(64))"
  ```
- Optionally set `LLM_PROVIDER` to `anthropic` or `ollama` and supply the relevant keys.

### Run migrations

```sh
alembic upgrade head
```

Verify the migration chain reaches the current head:

```sh
alembic current
```

Expected output ends with `(head)` on revision `4df931a7000b`.

### Seed development data

```sh
python seed.py
```

This creates one user (`jane.doe@university.ac.uk` / `password`), sample projects, findings, and learning resources. Safe to re-run — duplicate-safe via ON CONFLICT.

### Start the API server

```sh
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health`

---

## 3. Frontend

```sh
cd frontend
pnpm install
pnpm dev
```

The Vite dev server starts on port **8443**. Open `http://localhost:8443` in a browser and log in with the seed credentials.

For a production build:

```sh
pnpm build
```

---

## 4. Run the test suite

```sh
cd backend
pytest -q -m "not slow"
```

All 257 non-slow tests should pass. The slow test (`-m slow`) runs Semgrep against a real ZIP; skip it in CI unless Semgrep and the registry are available.

---

## 5. AI providers (optional)

The AI features (explain, assistant, suggested fix) are disabled by default (`LLM_PROVIDER=none`). All affected endpoints return **503** when the provider is `none` — this is intentional and not a bug.

**Anthropic:**
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5
```

**Ollama (local):**
```
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

---

## 6. Known limitations

- **Background jobs do not survive server restart.** Any job in `running` state when the server stops is reset to `failed` on the next startup. Resubmit the source archive to re-run.
- **No rate limiting.** Deploy behind a reverse proxy (nginx, Caddy) and add rate limiting there for any internet-facing deployment.
- **JWT has no server-side revocation.** Tokens expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 60 minutes). Log out clears the token from `sessionStorage` on the client only.
- **CodeAnalysis screen** shows demo data — not connected to live job metrics in this release.

---

## 7. Security notes

- Never commit `.env` or `uploads/` — both are in `.gitignore`.
- Rotate `JWT_SECRET_KEY` to invalidate all existing sessions.
- The `uploads/` directory contains extracted user source files. Ensure it is on a volume not served by a web server.
- `failure_reason` on failed analysis jobs is visible to all project members but has server paths replaced with `<source_dir>` before storage.
