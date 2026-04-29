# Apparel Line Balancing — AI-Powered (Phases 1 + 2 + 3)

AI-assisted line balancing for cut-make-trim apparel factories. Replaces
Excel-based RPW spreadsheets with a CP-SAT solver, role-based web UI and a
Claude-powered "what-if" explanation layer.

## What's included

**Phase 1** — master data, CP-SAT solver, Claude advisor, balance wizard,
layout visualiser. **Phase 2** — real-time re-balancing trigger + diff,
bottleneck dashboard with WIP and root-cause analysis. **Phase 3** —
mobile time-study capture, IoT telemetry ingestion + utilisation,
Odoo-compatible REST integration.

## Phase 1

- **Master data**: Styles, Operations (with precedence), Operators (with
  per-operation efficiency matrix), Machines, Lines.
- **Balancing engine**: Google OR-Tools **CP-SAT** with an RPW heuristic seed
  (`backend/app/services/solver.py`). Optimises the bottleneck cycle time
  subject to precedence, skill-match, machine-availability and one-operator-
  per-station constraints.
- **AI advisor**: Claude (Sonnet 4.6 by default) generates a narrative
  summary of the run and answers free-text what-if questions
  (`backend/app/services/claude_advisor.py`).
- **REST API** (FastAPI, OpenAPI at `/docs`):
  - `POST /api/auth/login`, `GET /api/auth/me`
  - CRUD for `lines`, `machines`, `operators`, `styles`
  - `POST /api/balance/run`, `GET /api/balance/runs`,
    `GET /api/balance/runs/{id}`, `POST /api/balance/runs/{id}/explain`,
    `POST /api/balance/runs/{id}/apply`
  - `POST /api/imports/operation-bulletin/{style_id}` (CSV/XLSX)
- **Frontend** (React 18 + TypeScript + Tailwind + shadcn/ui):
  - Login + role-based shell (Admin / Production Manager / Supervisor / IE)
  - Master-data screens (lines, machines, operators, styles)
  - **Balance Wizard** (style → line → target → operators → solve)
  - **Layout visualiser** with station heatmap, bottleneck callout and
    operator-by-operator table
  - Mobile-responsive (tested on tablet width)
- **Sample data**: a basic pique polo shirt with **35 operations**, full
  precedence, **25 operators** with a generated skill matrix, **42
  machines**, two lines. Auto-loaded on first startup.
- **Docker Compose**: Postgres 16 + backend + frontend + nginx in one
  command.

## Architecture

```
┌────────────────────┐       ┌──────────────────────────┐
│  React + TS + Vite │  /api │  FastAPI (Python 3.12)   │
│  Tailwind, shadcn  │──────▶│  ┌────────────────────┐  │
│  TanStack Query    │       │  │ Routers: auth,     │  │
│  Mobile-responsive │       │  │  lines, machines,  │  │
│  served via nginx  │       │  │  operators, styles,│  │
└─────────┬──────────┘       │  │  balance, imports  │  │
          │                  │  └────────┬───────────┘  │
          │                  │           │              │
          │                  │  ┌────────▼───────────┐  │
          │                  │  │ Solver (OR-Tools   │  │
          │                  │  │  CP-SAT) + RPW seed│  │
          │                  │  └────────┬───────────┘  │
          │                  │           │              │
          │                  │  ┌────────▼───────────┐  │
          │                  │  │ Claude Advisor     │  │
          │                  │  │  (Anthropic API)   │  │
          │                  │  └────────┬───────────┘  │
          │                  └───────────┼──────────────┘
          │                              │
          │                  ┌───────────▼──────────────┐
          └─────────────────▶│   PostgreSQL 16 + pgcrypto│
                             │   (db/init.sql)           │
                             └──────────────────────────┘
```

## Quick start (Docker)

```bash
cp .env.example .env          # add your ANTHROPIC_API_KEY (optional)
docker compose up --build
```

| URL                        | What                              |
|----------------------------|-----------------------------------|
| http://localhost:3000      | Frontend                          |
| http://localhost:8000/docs | OpenAPI / Swagger UI              |
| http://localhost:8000/redoc| ReDoc                             |
| postgres://localhost:5432  | Postgres (postgres / postgres)    |

### Default seeded users

| Username | Password | Role               |
|----------|----------|--------------------|
| admin    | admin123 | ADMIN              |
| pm1      | pm123    | PRODUCTION_MANAGER |
| sup1     | sup123   | SUPERVISOR         |
| ie1      | ie123    | IE                 |

## Local dev (no Docker)

```bash
# 1. DB
docker run -d --name lb_db -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=line_balancing \
  -v "$PWD/db/init.sql:/docker-entrypoint-initdb.d/00-init.sql:ro" \
  postgres:16-alpine

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. Frontend
cd ../frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The frontend dev server proxies `/api` to
`http://localhost:8000`.

## Try the polo-shirt sample

1. Log in as `ie1 / ie123`.
2. **Balance Wizard** → Style **POLO-001**, Line **L1**, target **60/hr**.
3. Solve. You'll see takt, theoretical ops, station heatmap, the
   operator-by-operator layout, and (if `ANTHROPIC_API_KEY` is set) a
   Claude-generated narrative.
4. Try a what-if: "What if we drop to 12 operators?" — the answer is grounded
   in the run's actual numbers.

## Importing your own bulletin

Send a CSV/XLSX to `POST /api/imports/operation-bulletin/{style_id}` with
columns: `op_code, sequence, description, sam, machine_type, skill_level,
section, predecessors`. A working example is in
[`docs/sample_operation_bulletin.csv`](docs/sample_operation_bulletin.csv).

## Solver contract

Located in `backend/app/services/solver.py`. Inputs:

| Field                 | Type                              | Notes                                                          |
|-----------------------|-----------------------------------|----------------------------------------------------------------|
| `operations`          | `list[OpDTO]`                     | dense indices, with SAM, machine_type, skill_level             |
| `operators`           | `list[OperatorDTO]`               | dense indices, with base_efficiency %                          |
| `precedence`          | `list[(pred_idx, succ_idx)]`      | enforced as `station(pred) <= station(succ)`                   |
| `skill_matrix`        | `dict[(op_idx, op_idx) -> eff %]` | absent entries treated as not-certified                        |
| `machines_available`  | `dict[str -> int]`                | per type cap on simultaneous stations                          |
| `target_output_hour`  | `int`                             | drives takt and theoretical ops                                |
| `working_minutes`     | `int`                             | for daily target arithmetic                                    |

Output (`SolverResult`): `assignments`, `station_cycle_min`, `takt_time`,
`line_efficiency` %, `balance_loss` %, `bottleneck_station`, plus solver
status and warnings.

### Extending the solver

- **Multiple operations per station / station capacity**: already supported
  — a station's load is the sum of its assigned ops' cycle times.
- **Mixed machine stations** (rare): set `machines_available[type] >=
  n_stations` and add a `station_machine_type` decision variable; today the
  model assumes a single machine type per station via the `uses_*` constraint.
- **Genetic refinement**: replace `_heuristic_seed` with an external GA
  pass — its return value is fed in as a CP-SAT hint, so any feasible seed
  helps convergence.
- **Multi-objective** (e.g. maximise efficiency *and* minimise idle hot
  stations): switch `model.Minimize(cycle_time_var)` to a weighted sum or
  use OR-Tools' `AddDecisionStrategy`.

## Roles

- **ADMIN** — manage users + everything below.
- **PRODUCTION_MANAGER** — full master-data + balance + apply.
- **IE** — master data + balance run (cannot apply to line).
- **SUPERVISOR** — read-only master data, run balances, apply.
- **OPERATOR** — read-only.

The `require_role` dependency is in `backend/app/auth/security.py`.

## Phase 2 — real-time re-balancing + bottleneck dashboard

**Triggers** (any one fires a "re-balance suggested" banner on the dashboard;
poll `GET /api/rebalance/check?line_id=…`):

| Trigger              | How it's detected                                       |
|----------------------|---------------------------------------------------------|
| `OPERATOR_ABSENT`    | Operator on the active run has `attendance_status != PRESENT` |
| `MACHINE_BREAKDOWN`  | Any machine on the line has `status = BREAKDOWN`        |
| `OUTPUT_DEVIATION`   | Last hour actual vs target deviates more than ±15%      |
| `TARGET_CHANGE`      | UI / API supplies a new `target_output_hour`            |
| `MANUAL`             | User clicks "Propose new balance"                       |

**Propose** (`POST /api/rebalance/propose`):
- Re-runs the solver with current `PRESENT` operators and
  `WORKING/IDLE` machines.
- Persists a new `BalanceRun` and a `RebalanceEvent` linking it to the
  previous run.
- Returns a station-by-station diff with `eff_before / eff_after` and
  `delta_output / hr` so the supervisor can see impact before accepting.

**Decide** (`POST /api/rebalance/events/{id}/decide`):
- `accepted=true` marks the new run `APPLIED` and demotes the previous
  one to `REJECTED`.

**Bottleneck dashboard** (`GET /api/dashboard/bottleneck?line_id=…`):
- Station-level heatmap (red >100% / amber 95–100% / green 85–95% /
  blue <85%) with the bottleneck station ringed in red.
- WIP per station with critical/warning alerts when units exceed the
  per-station threshold.
- Heuristic root-cause analysis (`backend/app/services/root_cause.py`)
  suggesting one or more of: `skill_gap`, `machine`, `method`, `layout`
  — each with a concrete suggestion (cross-train operator X, repair
  machine Y, re-do method study, split station Z).
- Hourly production capture form so the deviation trigger has data.

**WIP capture**: `POST /api/production/wip { run_id, station, wip_units, threshold }`
**Hourly capture**: `POST /api/production/hourly { line_id, run_id?, hour_slot, target, actual }`

## Phase 3 — mobile time study, IoT, Odoo

**Time study** (`/time-study` page, `POST /api/time-studies`):
- Mobile-friendly screen with built-in stopwatch (`Start` / `Lap` / `Stop`),
  rating + allowance inputs, and a captured-vs-standard SAM preview.
- Server stores `cycle_seconds`, `rating`, `allowance` and computes
  `captured_sam = (cycle/60) * (rating/100) * (1 + allowance/100)` as a
  Postgres generated column.
- `GET /api/time-studies/aggregate?style_id=…` returns per-op
  averages with `flag = high | low | ok` when deviation from standard
  is ≥ 10%. The bottleneck root-cause service feeds on this signal.

**IoT machine telemetry**:
- `POST /api/iot/telemetry` accepts batches of
  `{machine_code, is_running, rpm?, captured_at?, payload?}` events.
  Auto-flips machine status (IDLE ⇄ WORKING) on the latest event.
- `GET /api/iot/utilisation?line_id=…&minutes=60` returns each machine's
  running %, average RPM and last-seen timestamp over the window.
- `/iot` page renders this as a real-time utilisation table.

**Odoo 18 integration** (`/api/odoo/*`):
- `POST /api/odoo/search_read` mirrors Odoo's `search_read` semantics
  (model + domain + fields + limit/offset). Six models are exposed:
  `lb.style`, `lb.operation`, `lb.operator`, `lb.machine`,
  `lb.balance_run`, `lb.balance_assignment`.
- A tiny domain parser supports `=, !=, in, not in, >, <, >=, <=, ilike`.
- `POST /api/odoo/external-ids` stores the Odoo external-ID mapping
  (`erp_external_ids` table) so re-syncs are idempotent.

```
# Example: list all SNLS machines from Odoo's side
curl -X POST http://localhost:8000/api/odoo/search_read \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"model":"lb.machine","domain":[["type","=","SNLS"]],"limit":50}'
```

## Pages added in Phase 2/3

| Path                         | What                                                    |
|------------------------------|---------------------------------------------------------|
| `/bottleneck`                | Heatmap + root-cause + WIP / hourly capture             |
| `/rebalance/events/:id`      | Before-vs-after diff and accept/reject buttons          |
| `/time-study`                | Mobile stopwatch + rating/allowance + style aggregate   |
| `/iot`                       | Live machine utilisation gauges                         |

## Repo layout

```
backend/
  app/
    main.py            FastAPI app factory + lifespan
    config.py          Pydantic settings (env-driven)
    database.py        SQLAlchemy engine + session
    models/            ORM models (User, Line, Machine, Operator, Style,
                       Operation, Precedence, BalanceRun, ...)
    schemas/           Pydantic request/response schemas
    routers/           HTTP endpoints (one file per resource)
    services/
      solver.py        OR-Tools CP-SAT line balancer (+ RPW seed)
      claude_advisor.py Anthropic Claude integration
    auth/              JWT + bcrypt + role guards
    seed/              Idempotent bootstrap (admin user, polo style, ops)
  tests/               Solver smoke test
  Dockerfile

frontend/
  src/
    main.tsx, App.tsx
    components/Shell.tsx, components/ui/*  (shadcn-style primitives)
    pages/
      LoginPage.tsx, Dashboard.tsx
      LinesPage.tsx, MachinesPage.tsx, OperatorsPage.tsx
      StylesPage.tsx, StyleDetailPage.tsx
      BalanceWizard.tsx, BalanceResultPage.tsx
    lib/api.ts, lib/auth.ts, lib/utils.ts
    types/index.ts
  Dockerfile, nginx.conf

db/init.sql           Full PostgreSQL schema (+ Phase 2/3 stub tables)
docs/                 Sample CSV bulletin
docker-compose.yml
.env.example
```
