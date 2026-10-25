# AI Pentest Platform

An AI-assisted penetration-testing and remediation platform. See [`docs/`](./docs)
for the full design (verification engine, coverage matrix, state machine,
evaluation plan, architecture, and the platform's own hardening spec).

> **Milestone 2 status — real scanning (no automated fixes yet).**
> Real scans run actual security tools (Bandit, detect-secrets, pip-audit, and a
> safe passive dynamic checker) in **isolated worker processes**. Mock sample
> scans remain available and are always labelled. There is still **no automated
> code modification** — the "Generate Fix" button is a placeholder.
> See [`docs/milestone-2-scanners.md`](./docs/milestone-2-scanners.md).

## What's here

- **`backend/`** — FastAPI + SQLAlchemy. Health checks, PostgreSQL-compatible
  models (projects, scan jobs, findings), a modular **scanner framework**
  (`app/scanners/`), **isolated workers** (`app/workers/`), and a placeholder
  "Generate Fix" endpoint. Tests run on in-memory SQLite.
- **`frontend/`** — Next.js + TypeScript. Dashboard, Targets (add web target /
  connect repo), Scan History (mock/real mode + coverage report), and Findings
  (severity, confidence, evidence, status, scanner provenance).
- **`docs/`** — the design specifications and the M2 scanner notes.
- **`docker-compose.yml`** — optional local PostgreSQL.

> **Upgrading from Milestone 1:** the database schema gained columns. If you ran
> M1 and have a `backend/dev.db`, delete it so the new schema is created:
> `del backend\dev.db` (Windows) / `rm backend/dev.db`.

## Prerequisites

- Python 3.11+ (tested on 3.14)
- Node.js 18+ (tested on 25)
- PostgreSQL is **optional** — the backend defaults to a local SQLite file so
  you can start with zero database setup.

## Run it locally (two terminals)

### 1. Backend (terminal A)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate           # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Interactive API docs: http://localhost:8000/docs
- On first start it creates the database and seeds sample mock data.

### 2. Frontend (terminal B)

```powershell
cd frontend
npm install
copy .env.local.example .env.local    # Windows  (cp on macOS/Linux)
npm run dev
```

- App: http://localhost:3000

Open http://localhost:3000, and you'll see the dashboard populated with the
seeded mock scans and findings. Add a target on the **Targets** page, then from
**Scan History** choose a mode and run a scan:

- **Real scan of a repository:** add a **repo** target whose URL is a local
  folder path (e.g. `D:\code\my-app`) or a reachable git URL, then run a real
  scan. Bandit, detect-secrets and pip-audit run in an isolated worker and
  results appear under **Findings**. Use the **Coverage** button to see which
  scanners ran, were skipped, or errored.
- **Real scan of a web target:** add a **web** target (confirming authorization).
  The safe passive dynamic checker inspects the authorized origin's security
  headers/cookies only.

Real scans run in a separate process, so the row shows `queued` → `running` →
`completed`; the page refreshes automatically while a scan is active.

## Using PostgreSQL instead of SQLite (optional)

```powershell
docker compose up -d
cd backend
pip install "psycopg[binary]"         # PostgreSQL driver
$env:DATABASE_URL = "postgresql+psycopg://aipentest:devpassword@localhost:5432/aipentest"
uvicorn app.main:app --reload --port 8000
```

(The `devpassword` is a local-only development value — see
[`docs/platform-hardening-spec.md`](./docs/platform-hardening-spec.md) for how
secrets are handled properly.)

## Run the tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Known follow-ups (tracked, not blocking M1)

- Frontend has transitive `postcss` dev-dependency advisories inherited from the
  Next.js 15 line; upgrading resolves them but requires a Next 16 major bump,
  deferred to avoid destabilising this milestone.
- Authentication, database row-level security, and rate limiting are specified
  in `docs/platform-hardening-spec.md` and land in the next milestone.
