# AI-based Smart Mining Governance & Compliance System

Compliance governance for mineral concessions: a lease register, statutory
clearances, a derived compliance calendar, and explainable risk scoring.

Built feature by feature. **Steps 1 and 2 are complete and verified**: the
compliance API, and a responsive web interface that works on a phone and on a
desktop. See [Roadmap](#roadmap) for what comes next.

---

## What is built

### Step 1 - Compliance API

The lease is the aggregate root of the domain - every clearance, filing,
inspection and violation attaches to one. So the register came first.

| Capability | Status |
| --- | --- |
| Lease registry with PostGIS boundaries and centroids | ✅ |
| Statutory clearances with expiry tracking | ✅ |
| Obligation *rules* stored as data, not code | ✅ |
| Derived compliance calendar (18 months of filings per lease) | ✅ |
| Explainable compliance score + risk banding | ✅ |
| Portfolio dashboard rollup | ✅ |
| Spatially filtered lease queries (bounding box, GeoJSON export) | ✅ |
| Idempotent seed with an India/MMDR reference pack | ✅ |
| Test suite: 130 tests, lint clean | ✅ |

### Step 2 - Web interface

Mobile-first, not desktop-with-media-queries. The layout reflows on its own and
nothing important is hidden behind a dropdown on a small screen.

| Capability | Status |
| --- | --- |
| Dashboard: KPI tiles, risk distribution, state and category breakdown | ✅ |
| Lease register: filters, search, sort, pagination | ✅ |
| Lease detail: map, clearances, score breakdown, filing timeline | ✅ |
| Site map: MapLibre boundaries with tap-for-detail popups | ✅ |
| Compliance calendar grouped by month, file-state filters | ✅ |
| Typecheck, lint and production build all clean | ✅ |

#### How the interface stays comfortable on both

| Concern | Phone | Desktop |
| --- | --- | --- |
| Navigation | Sticky header + bottom tab bar, safe-area padded | Fixed 264px sidebar |
| Data grid | Card list with the same data | Full 9-column table |
| Tap targets | 44px minimum (`min-h-11`, `min-h-14`) | Dense 32-36px controls |
| Dashboard tiles | 2 columns | 3, then 4 |
| Lease detail | Map full width, then single column | Map full width, then 2 + 1 columns, score sticky |
| Filters | Reflow to a 2-column grid, native OS pickers | Single row |

Notably, the register renders a card list *and* a table, both in the DOM, and
swaps them with CSS rather than JavaScript. That avoids a layout shift on resize
and keeps the page a server component.

### Two design decisions worth knowing

**Rules are data.** An obligation rule says *"due N days after the reporting
period ends"*, and the fiscal year end is a field. The engine that generates the
calendar has no knowledge of India, the MMDR Act, or a March year end - it is
all just rows. Adding a second jurisdiction is a seed change, not a code change.

**The compliance score is derived, never stored.** It recomputes from the
underlying records on every read, so nothing can drift out of sync and
re-running it is always safe. Components that have no data (a lease registered
last week with nothing due yet) are *excluded and their weight redistributed*
rather than scored as failures - otherwise every new lease would read as
non-compliant and the number would become noise operators learn to ignore.

The score is also explainable. `GET /leases/{id}/compliance` returns each
weighted component with its own detail string:

```
ML/OD/2009/0231  score=59.9  risk=high
  [x] clearance_validity    10.0/40.0  1 of 4 clearance(s) currently valid
  [x] filing_adherence     42.35/45.0  16 of 17 due filing(s) submitted
  [x] timeliness             7.5/15.0  8 of 16 submission(s) filed on or before the due date
  notes:
    - 3 clearance(s) lapsed or revoked.
    - 1 clearance(s) expire within 90 days.
    - 1 obligation(s) overdue.
```

---

## Architecture

```
apps/web          Next.js 16 + Tailwind v4 + shadcn/ui   <- implemented
services/api      FastAPI + SQLAlchemy                   <- implemented
infra             Docker Compose: PostGIS + pgvector + Redis
```

PostgreSQL carries **both PostGIS and pgvector**. No upstream image ships both,
so `infra/db/Dockerfile` layers pgvector onto the official PostGIS image. PostGIS
is used now for boundaries and geodesic area; pgvector is enabled and waiting for
semantic search over regulations in a later step.

### Layout

```
services/api/
  app/
    api/v1/        HTTP routers      (reference, leases, licences,
                                      obligations, calendar, dashboard)
    models/        SQLAlchemy ORM    (the aggregate + controlled vocabularies)
    schemas/       Pydantic I/O
    services/      business logic    (calendar, compliance, geo, leases, ...)
    db/            seed + reference pack
  alembic/         migrations
  tests/           130 tests

apps/web/
  app/             routes: dashboard, leases, leases/[id], map, calendar
  components/      app shell + domain components; components/ui holds shadcn
  lib/             api client, formatters, types, load helper
```

Business logic lives in `services/`, not in the routers, so the scoring and
scheduling rules are testable without spinning up HTTP.

---

## Running it

**Prerequisites:** Docker, Python 3.12+, [uv](https://docs.astral.sh/uv/).

### 1. Start the infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d
```

PostgreSQL is published on **5434**, not 5432, because a local PostgreSQL very
often owns 5432 already. Override with `POSTGRES_PORT` if needed.

Verify both extensions landed:

```bash
docker exec mg-postgres psql -U mining -d mining_governance \
  -c "SELECT extname FROM pg_extension ORDER BY 1;"
```

### 2. Apply migrations and seed

```bash
cd services/api
uv sync
uv run alembic upgrade head
uv run python -m app.db.seed
```

The seed is idempotent - running it twice creates nothing new and refreshes
dates instead of duplicating the register. It loads 10 minerals, 4 holders, 12
obligation rules, 10 concessions across 8 states, and a simulated filing history
(53 on time, 64 late, 27 genuinely overdue) so the risk views have something
real to show.

> All seeded entities and identifiers are fictitious (`DEMO-CIN-...` prefixes).
> Royalty rates and deadlines are **illustrative development defaults** - verify
> against the current statute before relying on them.

### 3. Run the API

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Interactive docs at <http://localhost:8000/docs>.

### 4. Run the web interface

```bash
pnpm install          # from the repo root
pnpm dev:web          # http://localhost:3000
```

The web app reads `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`),
so start the API first or every page will show a "could not reach the compliance
API" notice - which names the command to run rather than failing silently.

### 5. Test and build

```bash
# Backend
cd services/api
uv run pytest -q              # 130 tests
uv run ruff check app tests   # lint

# Frontend
cd apps/web
pnpm typecheck && pnpm lint && pnpm build
```

Database tests create and drop a `<database>_test` database automatically, and
skip cleanly (rather than failing) when no PostgreSQL is reachable.

---

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health/ready` | Readiness + PostGIS version |
| `GET` | `/api/v1/dashboard/summary` | Portfolio rollup |
| `GET/POST` | `/api/v1/leases` | Register: filter by state, bbox, risk, expiry |
| `GET` | `/api/v1/leases/geojson` | Whole register as one GeoJSON FeatureCollection, for the map |
| `GET/PATCH/DELETE` | `/api/v1/leases/{id}` | Lease detail |
| `GET` | `/api/v1/leases/{id}/compliance` | Explainable score breakdown |
| `GET` | `/api/v1/leases/{id}/licences` | Clearances with days-to-expiry |
| `POST` | `/api/v1/leases/{id}/obligations/generate` | Materialise the calendar |
| `GET` | `/api/v1/calendar` | Cross-lease calendar (`entry_state=` overdue, due_soon, upcoming, filed) |
| `POST` | `/api/v1/calendar/{id}/submit` | Record a filing |
| `PATCH` | `/api/v1/calendar/{id}` | Waive, reopen, or mark not applicable |
| `POST` | `/api/v1/calendar/refresh` | Recompute overdue status |
| `GET/POST` | `/api/v1/obligations` | Obligation rules |
| `GET/POST` | `/api/v1/minerals`, `/api/v1/holders` | Reference data |
| `GET` | `/api/v1/clearances/expiring` | Clearance expiry queue |

Every read that depends on "now" accepts `?as_of=YYYY-MM-DD`, so an auditor can
ask what the position was on a specific date and get the answer the system gave
then.

### Lease filtering

```
GET /api/v1/leases?state=Odisha&risk_level=high&expiring_within_days=90
GET /api/v1/leases?bbox=85.0,20.0,86.5,22.5&sort=compliance_score
GET /api/v1/leases?q=chromite&status=active&status=pending_renewal
```

---

## Roadmap

Each step is a vertical slice: schema, API, tests, then UI.

| Step | Feature | Notes |
| --- | --- | --- |
| **1** | **Lease registry + compliance calendar (API)** | ✅ **Done** |
| **2** | **Web interface: dashboard, register, map, calendar** | ✅ **Done** |
| 3 | Supabase Auth + roles; audit trail on every mutation | `submitted_by` is currently free text, deliberately |
| 4 | Document ingestion + AI extraction (Gemini/Groq, LangGraph) | `Licence.document_path` and `evidence_path` already exist to receive them |
| 5 | Violation detection + pgvector search over regulations | Extensions already enabled |
| 6 | Royalty computation and return drafting | `royalty_basis` / `royalty_rate` already modelled per mineral and per lease |
| 7 | Workflow notifications, Celery + Redis scheduled checks | Redis is already running |

### Known gaps

Being explicit about what is *not* done yet:

**Both steps**
- No authentication. Intended for Step 3, alongside the audit trail.
- No audit log - mutations are not yet attributable.

**API**
- `submitted_by` is free text until real identities exist.
- One-time obligations need an explicit due date, and there is no input for it yet.
- Dashboard scoring walks all lease ids; fine at hundreds, wants caching at tens of thousands.
- Spatial queries are not yet index-tuned beyond the default GIST indexes.

**Web**
- The interface is read-only: filing a return, waiving an obligation and editing a
  lease are all still API-only. The mutations exist and are tested; nothing calls
  them yet.
- No loading skeletons or optimistic updates.
- Cell-level rendering is not virtualised, so very long lists will feel heavy.
- Dark mode follows the system preference only; there is no toggle.

---

## Testing notes

`tests/test_calendar_math.py` and `tests/test_compliance_scoring.py` are pure
unit tests with no database, covering the fiscal arithmetic and the scoring
policy. The fiscal maths is where an off-by-one silently makes every filing
deadline in the product wrong, so it is tested against a table of known dates
including leap years and a December year-end variant.

The remaining suites are integration tests against real PostgreSQL, because the
code depends on PostGIS geometry, array columns and filtered aggregates that
SQLite cannot represent.
