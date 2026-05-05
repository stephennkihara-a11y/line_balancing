# Deployment Guide

Practical, step-by-step deployment options for the Apparel Line Balancing
system, ordered from simplest to most production-ready. **Pick one path
based on your scale, ops capacity, and how much of the factory floor
needs offline-tolerant access.**

| Path | Best for | Effort | Monthly cost (rough) |
|------|----------|--------|----------------------|
| **A. On-prem single VM (Docker Compose)** | Pilot or single factory, sensitive data must stay on-site | ½ day | $0 (own hardware) — $20 (small VPS) |
| **B. Managed PaaS** (Render / Railway + Vercel + Neon) | Fast SaaS-style rollout, no ops team | 2 hours | $30–$80 |
| **B-free. Render free + Cloudflare Pages + Neon free** | Demo, pilot, or tiny single-line factory | 45 min | **$0** |
| **C. Cloud VM with reverse proxy** (Hetzner / DO / Lightsail + Caddy) | Predictable cost, full control, single region | 1 day | $10–$40 |
| **D. Kubernetes (EKS / GKE / k3s)** | Multi-factory, scale > 10 concurrent solvers, in-house DevOps | 1 week | $200+ |
| **E. Hybrid: on-prem floor + cloud sync** ⭐ | Real apparel factories with floor tablets + cross-site reporting | 2–3 days | $20 cloud + own server |

⭐ = recommended for a real apparel factory.

---

## 0. Pre-deployment checklist (every path)

Before touching production:

1. **Generate a real `JWT_SECRET`** (32+ chars):
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
2. **Get an Anthropic API key** from <https://console.anthropic.com/>
   if you want the Claude advisor + what-if narrative.
3. **Change all default passwords** — the seed creates `admin/admin123`,
   `pm1/pm123`, `sup1/sup123`, `ie1/ie123`. **Rotate them immediately
   after first login** and create real users via `POST /api/auth/users`.
4. **Set `cors_origins`** to only your real frontend URL(s).
5. **Pin tags, not `latest`** — bake a version into the Docker image
   (`backend:0.1.0`) so rollbacks are deterministic.
6. **Plan backups** — Postgres is the source of truth.

`.env` for production should look like:

```bash
JWT_SECRET=<48-byte token from above>
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
ENVIRONMENT=production
CORS_ORIGINS=["https://lb.factory.com"]
SOLVER_TIME_LIMIT_S=30
DATABASE_URL=postgresql+psycopg2://lb_user:<strong-pw>@db:5432/line_balancing
```

---

## Path A — On-prem single VM (Docker Compose)

Best when you already have a small Linux server in the factory rack and
don't want any cloud dependency.

### A.1 Provision

- 4 vCPU / 8 GB RAM / 80 GB SSD is plenty for one factory (the CP-SAT
  solver is the main CPU consumer; everything else is light).
- Ubuntu 24.04 LTS or Debian 12.
- Open inbound ports 80 + 443 only.

### A.2 Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

### A.3 Pull the code, configure, run

```bash
git clone <your-fork> /opt/line-balancing
cd /opt/line-balancing
cp .env.example .env
$EDITOR .env                      # JWT_SECRET, ANTHROPIC_API_KEY, etc.
docker compose pull && docker compose up -d --build
docker compose logs -f backend    # watch alembic migrations + bootstrap
```

Visit `http://<server-ip>:3000`. Log in as `admin / admin123` and
**change the password immediately**.

### A.4 Add HTTPS with Caddy (one config file, auto Let's Encrypt)

Add a `caddy` service to `docker-compose.yml`:

```yaml
caddy:
  image: caddy:2-alpine
  restart: unless-stopped
  ports: ["80:80", "443:443"]
  volumes:
    - ./Caddyfile:/etc/caddy/Caddyfile:ro
    - caddy_data:/data
  depends_on: [frontend, backend]
volumes:
  caddy_data:
```

`Caddyfile`:

```caddy
lb.factory.com {
    encode gzip
    handle /api/* {
        reverse_proxy backend:8000
    }
    handle {
        reverse_proxy frontend:80
    }
}
```

Point your DNS A record to the server, restart compose, Caddy auto-issues
a TLS cert in ~10 seconds. Now remove the public `8000` and `3000` port
mappings from `backend` and `frontend` — only Caddy needs to be exposed.

### A.5 Backups (cron)

```bash
sudo crontab -e
0 2 * * * docker exec line-balancing-db-1 pg_dump -U postgres line_balancing | gzip > /backups/lb-$(date +\%F).sql.gz
0 3 * * 0 find /backups -name 'lb-*.sql.gz' -mtime +30 -delete
```

Sync `/backups` off-site weekly (rclone to Backblaze B2 or S3).

---

## Path B — Managed PaaS (zero-ops SaaS-style)

Fastest way to put it on the public internet without managing servers.

### Architecture

```
            ┌──────────────────┐
            │   Vercel /       │   Static SPA (Vite build)
            │   Cloudflare     │
            │   Pages          │
            └────────┬─────────┘
                     │ /api/* proxied
            ┌────────▼──────────┐
            │  Render /         │   FastAPI container
            │  Railway /        │   (1 Web service + 1 worker for big
            │  Fly.io           │    solves if needed)
            └────────┬──────────┘
                     │
            ┌────────▼──────────┐
            │  Neon /           │   Managed Postgres 16
            │  Supabase /       │
            │  Railway Postgres │
            └───────────────────┘
```

### B.1 Database

Sign up to Neon (<https://neon.tech>) → create a project → copy the
connection string. It looks like
`postgresql://user:pw@ep-cool.eu-central-1.aws.neon.tech/db?sslmode=require`.
Convert to SQLAlchemy form: prepend `+psycopg2`:
`postgresql+psycopg2://...`.

### B.2 Backend on Render (similar on Railway/Fly)

1. New → **Web Service** → connect this repo, branch
   `claude/ai-line-balancing-system-KMhsO` (or your `main`).
2. **Root directory**: `backend`. **Dockerfile path**: `Dockerfile`.
3. Environment variables:
   - `DATABASE_URL` = your Neon URL
   - `JWT_SECRET`, `ANTHROPIC_API_KEY`, `CORS_ORIGINS`
4. Health check: `/api/health`.
5. Plan: `Standard` ($25/mo) — gives you 2 GB RAM which CP-SAT needs.
6. Deploy. Migrations + seed run automatically on first boot.

### B.3 Frontend on Vercel

1. New project → import the repo → **Root**: `frontend`.
2. Build command: `npm run build`. Output: `dist`.
3. Env var: `VITE_API_URL = https://lb-backend.onrender.com/api`.
4. Deploy. Vercel handles HTTPS + CDN.

Update the backend's `CORS_ORIGINS` to include your Vercel URL.

### B.4 Trade-offs

- ✓ Zero servers to babysit, free TLS, global CDN for the SPA.
- ✗ Cold starts on free tiers — solver requests can sit idle and stall.
  Use a paid plan or enable "always on".
- ✗ IoT telemetry to a public PaaS endpoint adds 20–80 ms vs LAN-local.
  If sensors are on the same WiFi, prefer Path A or E.

---

## Path B (free tier) — Render + Cloudflare Pages + Neon (zero $)

A truly $0/month deployment that's fine for **demos, pilots, and small
single-line factories** but has real limits you should plan around.
Total time: ~45 minutes.

### What you get and what you give up

| Service | Free tier | What hurts |
|---------|-----------|-----------|
| **Cloudflare Pages** (frontend) | Unlimited static hosting + bandwidth, free TLS, OK for commercial use | None for our use |
| **Render** (backend) | 512 MB RAM, 0.1 CPU, spins down after **15 min of inactivity**, 750 hrs/month | Cold start ~30–60 s on first request after idle. CP-SAT solver may OOM on > 50-op styles. |
| **Neon** (Postgres 16) | 0.5 GB storage, branching, autosuspend after 5 min idle | First query after suspend takes ~1 s. |

> ⚠️ **Vercel's Hobby plan is "non-commercial only"** in its TOS. For a
> factory-facing app prefer **Cloudflare Pages** which has no such clause
> and a more generous bandwidth allowance.

### B-free.1 Database — Neon

1. Sign up at <https://neon.tech> with GitHub.
2. **Create project** → region close to your users → Postgres 16.
3. **Dashboard → Connection Details** → copy the *psycopg2* URL. It looks
   like:
   ```
   postgresql://lb_user:abc123@ep-cool.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Convert to SQLAlchemy form by inserting `+psycopg2`:
   ```
   postgresql+psycopg2://lb_user:abc123@ep-cool.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
   Save this — you'll paste it into Render in the next step.

### B-free.2 Backend — Render

1. Sign up at <https://render.com> with GitHub.
2. **New → Web Service** → connect this repo → branch
   `claude/ai-line-balancing-system-KMhsO` (or your fork's `main`).
3. Settings:
   - **Name**: `line-balancing-api`
   - **Root Directory**: `backend`
   - **Runtime**: Docker (auto-detected from `backend/Dockerfile`)
   - **Instance Type**: **Free** (512 MB / 0.1 CPU)
   - **Health Check Path**: `/api/health`
4. **Environment** → add:
   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | the SQLAlchemy URL from B-free.1 |
   | `JWT_SECRET` | run `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `ANTHROPIC_API_KEY` | `sk-ant-...` (or leave blank to use the deterministic fallback narrative) |
   | `ANTHROPIC_MODEL` | `claude-sonnet-4-6` |
   | `ENVIRONMENT` | `production` |
   | `CORS_ORIGINS` | `["https://lb.pages.dev"]` (placeholder; you'll update after B-free.3) |
   | `SOLVER_TIME_LIMIT_S` | `15` *(reduce from 30 to fit the 512 MB / 0.1 CPU envelope)* |
5. **Create Web Service**. The first build takes ~5 min (Docker, OR-Tools
   wheel is large). Watch the logs — you should see:
   ```
   INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial
   line_balancing.bootstrap   seed complete
   Uvicorn running on http://0.0.0.0:10000
   ```
6. Render gives you a URL like `https://line-balancing-api.onrender.com`.
   Test:
   ```bash
   curl https://line-balancing-api.onrender.com/api/health
   # {"status":"ok","environment":"production","version":"0.1.0"}
   ```

### B-free.3 Frontend — Cloudflare Pages

1. Sign up at <https://pages.cloudflare.com> with GitHub.
2. **Create application → Connect to Git** → pick this repo.
3. Build configuration:
   - **Framework preset**: Vite
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Root directory** (advanced): `frontend`
4. **Environment variables** → Production:
   - `VITE_API_URL` = `https://line-balancing-api.onrender.com/api`
5. **Save & deploy**. Cloudflare gives you `https://<project>.pages.dev`.
6. **Go back to Render → Environment** and update
   `CORS_ORIGINS = ["https://<project>.pages.dev"]`. Save → Render
   restarts automatically.

Visit your Pages URL → log in as `admin / admin123` → **change the
password immediately** and create real users via the API.

### B-free.4 Mitigating Render's cold start

Render free spins down after 15 minutes of no requests. The first
request after that wakes the container in ~30–60 s, which feels broken
to floor users. Two zero-cost mitigations:

**Option 1 — UptimeRobot keep-warm** (simplest)

1. Sign up at <https://uptimerobot.com> (free, 50 monitors).
2. **Add monitor** → HTTP(s) → URL `https://line-balancing-api.onrender.com/api/health`
   → interval **5 minutes**.
3. Done — Render now sees a request every 5 min and never spins down
   during business hours. (Render's terms allow this; just keep one
   monitor, not a dozen.)

**Option 2 — frontend warm-up on load**

Add to `frontend/src/main.tsx` *before* the `ReactDOM.createRoot`:

```ts
fetch(`${import.meta.env.VITE_API_URL}/health`).catch(() => {});
```

This fires a non-blocking warm-up the moment a tablet hits the page,
so by the time the user logs in the API is already responsive.

### B-free.5 Database keep-warm (optional)

Neon autosuspends after 5 min idle, adding ~1 s to the first query.
For a single-factory pilot this is fine. If you want it always-on:

- Upgrade Neon to Launch ($19/mo) — disables autosuspend, or
- Set up a Cloudflare Worker cron that hits `/api/health` every 4 min
  (Workers free tier is 100k requests/day).

### B-free.6 Realistic limits of this setup

This is a fine **pilot / demo / small factory** deployment. Things that
will break it:

| Symptom | Cause | Fix |
|---------|-------|-----|
| Solver times out on a 60-op style | 0.1 CPU + 15-s limit | Drop to ~30 ops, or upgrade Render to **Starter** ($7/mo, 0.5 CPU 512 MB) — solver fits comfortably |
| 502 / "Application failed to respond" intermittently | Render container OOM during a big solve | Same — upgrade or split solves into a worker queue |
| First click of the day is slow | Cold starts (Render + Neon) | UptimeRobot ping (above) |
| Postgres "too many connections" | Neon free has a 100-connection limit; the backend's pool is 10/20 | Reduce `pool_size` to 5 + `max_overflow=10` in `backend/app/database.py` |
| IoT telemetry batches dropped | 0.1 CPU can't keep up with > ~50 events/min | Move IoT ingest to a self-hosted MQTT bridge (Path A or E) |

### B-free.7 First $7/mo — when to spend it

The single highest-leverage upgrade is **Render Starter** ($7/mo):
0.5 CPU, 512 MB, **no spin-down**. It removes the cold-start problem
and gives the solver enough CPU for a typical 35-op polo style. Keep
Cloudflare Pages and Neon on free.

After that, the next $19 buys **Neon Launch** for an always-on DB and
4 GB storage — useful once you start collecting hourly production and
IoT telemetry over months.

### B-free.8 Cheat sheet

```bash
# Local prep (one-time)
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET

# 1. Neon: create project, copy psycopg2 URL, prepend "+psycopg2"
# 2. Render: New Web Service → backend root → Free instance
#    Env: DATABASE_URL, JWT_SECRET, ANTHROPIC_API_KEY, CORS_ORIGINS, SOLVER_TIME_LIMIT_S=15
# 3. Cloudflare Pages: New project → frontend root → Vite preset
#    Env: VITE_API_URL=https://<render-url>/api
# 4. Update Render's CORS_ORIGINS with the Pages URL
# 5. UptimeRobot: 5-min HTTP monitor on /api/health  (keeps Render warm)
# 6. Log in as admin/admin123, rotate passwords immediately
```

---

## Path C — Cloud VM with reverse proxy

Same as Path A but on a Hetzner CX22 / DigitalOcean droplet / AWS
Lightsail. Predictable monthly cost, full control, no PaaS lock-in.

Use `docker compose` exactly as in Path A. The only difference is the
DNS record points to a cloud IP and you might use AWS RDS instead of
the in-compose Postgres for snapshots / point-in-time recovery.

If you go this route and want managed Postgres, change
`DATABASE_URL` to your RDS endpoint and remove the `db` service from
`docker-compose.yml`.

---

## Path D — Kubernetes (multi-factory or > 10 concurrent solves)

Outline only — full Helm chart left for a follow-up. The shape:

- **Postgres**: managed (RDS, Cloud SQL) or via the
  [CloudNativePG](https://cloudnative-pg.io/) operator with PVC
  snapshots.
- **Backend Deployment**: 2 replicas behind a Service. Resource request
  `cpu: 1, memory: 1Gi`, limit `cpu: 2, memory: 2Gi`. Health probe on
  `/api/health`.
- **Frontend Deployment**: nginx serving `dist/`, 2 replicas, ClusterIP.
- **Ingress**: nginx-ingress or Traefik with cert-manager for TLS.
- **HPA**: scale backend on CPU > 70% — CP-SAT bursts hit one pod hard.
- **Solver workers** (optional): split balance solves into a worker
  Deployment using Celery/RQ + Redis so the API stays responsive when
  someone clicks "Solve" on a 60-op style.
- **Migrations**: a `Job` runs `alembic upgrade head` on each release;
  remove the in-process call from `lifespan`.
- **Secrets**: `Secret` for `JWT_SECRET` + `ANTHROPIC_API_KEY`. External
  Secrets Operator if you keep them in AWS Secrets Manager / Vault.

For a single-cluster on-prem deployment, **k3s** on three small servers
gives you 90% of the win with 10% of the operational complexity.

---

## Path E — Hybrid (recommended for apparel factories) ⭐

Most apparel factories already have a server room with the ERP
(Odoo, SAP, etc.) on-prem and tablets on the WiFi. The line-balancing
backend should sit next to the ERP for low latency and offline
tolerance, while a tiny cloud presence handles cross-site reporting.

```
        FACTORY FLOOR                          OFFICE / CLOUD
   ┌────────────────────────────┐         ┌──────────────────────────┐
   │  Tablets (PWA)             │         │  Cloud VM (read-only     │
   │  – Time study screen       │  ►nightly  reporting + Claude API │
   │  – Bottleneck dashboard    │  rsync  │  – Postgres replica      │
   │  – Hourly capture          │ ──────► │  – Same React SPA        │
   └─────────┬──────────────────┘         │  – Aggregates across     │
             │ LAN WiFi                   │    factories             │
   ┌─────────▼──────────────────┐         └──────────────────────────┘
   │ Server in factory rack     │
   │   • backend (FastAPI)      │
   │   • Postgres (primary)     │
   │   • Caddy (HTTPS via       │
   │     internal CA or         │
   │     Let's Encrypt DNS-01)  │
   │   • Existing Odoo           │
   │     + connector addon      │
   │   • IoT MQTT broker (opt.) │
   └─────────┬──────────────────┘
             │ Wired LAN
   ┌─────────▼──────────────────┐
   │ Sewing machines with       │
   │ IoT sensors → MQTT → /api/iot/telemetry
   └────────────────────────────┘
```

### E.1 Why this shape

- **Latency**: tablets and IoT sensors talk to the LAN server in
  ≤5 ms. Public-internet round-trips would visibly lag the stopwatch
  and IoT ingest.
- **Offline tolerance**: a power blip or ISP outage doesn't stop
  production capture; data syncs to the cloud when the link returns.
- **Data residency**: SAM, operator names, daily output stay on the
  factory subnet. Only aggregate KPIs leave to the cloud.
- **Cost**: one rack server pays for itself in months vs cloud egress
  for IoT telemetry.

### E.2 Provisioning steps

1. **Server**: 8-core / 16 GB / 500 GB SSD in the factory rack on a
   wired LAN with a static IP (e.g. `10.0.0.10`).
2. **Install Docker + clone repo + configure** as in Path A.
3. **DNS**: pick `lb.local.factory` and add it to the internal DNS, or
   use Caddy's [DNS-01 challenge](https://caddyserver.com/docs/automatic-https#dns-challenge)
   to get a real Let's Encrypt cert for an internal hostname.
4. **Cloud replica** (small Hetzner CX11): set up a read-only Postgres
   replica via `pg_basebackup` + streaming replication over a WireGuard
   tunnel. Run a second copy of the frontend pointing at the replica.
5. **IoT sensors**: most apparel sensor kits expose MQTT. Run an MQTT
   broker (`eclipse-mosquitto:2`) on the same server and a tiny bridge
   that subscribes and `POST`s to `/api/iot/telemetry` in batches of
   100.
6. **Odoo**: install the connector from `odoo/line_balancing_connector/`
   (see its README); it will sync every 15 minutes over the LAN.
7. **PWA on tablets**: add a `manifest.json` + service worker so the
   frontend installs as a home-screen app (steps below).

---

## Mobile / tablet specifics

Line supervisors on the floor need a **tablet-first** experience.

### Make the SPA installable as a PWA

Add `frontend/public/manifest.json`:

```json
{
  "name": "Line Balancing",
  "short_name": "LB",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#0f172a",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

Reference it from `frontend/index.html`:

```html
<link rel="manifest" href="/manifest.json" />
<meta name="theme-color" content="#0f172a" />
<meta name="apple-mobile-web-app-capable" content="yes" />
```

Add a service worker (e.g. via `vite-plugin-pwa`) that caches the JS
bundle + last `/api/dashboard/bottleneck` response so a flaky tablet
WiFi doesn't blank the screen.

### Lock tablets to the app

Use Android's [kiosk mode](https://developers.google.com/android/work/kiosk-mode)
or the built-in **App pinning** so supervisors can't accidentally
swipe out of the dashboard.

---

## Production hardening checklist

Before going live with real users:

- [ ] All default passwords rotated; old test users disabled.
- [ ] `JWT_SECRET` >= 48 bytes, stored in a secrets manager (not git).
- [ ] `CORS_ORIGINS` set to exactly your frontend URLs.
- [ ] HTTPS enforced (HTTP redirect, HSTS).
- [ ] Postgres `pg_hba.conf` only allows the backend's subnet.
- [ ] Postgres backups daily, off-site weekly, **restore tested** at
      least once.
- [ ] Application logs shipped to a central sink (Loki / Datadog /
      CloudWatch).
- [ ] Resource limits set on every container (`mem_limit`, `cpus`).
- [ ] Rate-limit `/api/iot/telemetry` (e.g. nginx
      `limit_req zone=iot burst=200 nodelay`) so a runaway sensor can't
      flood the DB.
- [ ] Image-scanning (`docker scout` or Trivy) in CI; rebuild monthly
      to pull base-image security fixes.
- [ ] Anthropic key has a per-month spend cap configured in the
      Anthropic console.
- [ ] `ENVIRONMENT=production` so debug endpoints (none today, but a
      future addition) won't leak.
- [ ] Replace the SQLite-friendly `Base.metadata.create_all` fallback
      in tests; production is alembic-only.

---

## Monitoring

Minimum useful set:

| Signal | Source | Alert when |
|--------|--------|-----------|
| `/api/health` reachable | uptime probe (UptimeRobot, Better Stack) | down for 3 min |
| Backend p95 latency | reverse-proxy access log → Loki/Promtail | > 2 s for 5 min |
| Postgres connections | `pg_stat_activity` | > 80% of `max_connections` |
| Postgres disk free | OS metric | < 20% |
| Solver duration | log line `Status: OPTIMAL ...` parsed by Promtail | > 25 s p95 |
| Anthropic spend | Anthropic console + monthly cap | 80% of cap |

For a one-server deployment, [Netdata](https://netdata.cloud/) covers
most of this with `apt install netdata` + a free cloud account.

---

## Scaling roadmap

When you outgrow Path A or E:

1. **Read replicas** for the dashboard + reporting endpoints
   (move `dashboard.py`, `iot.py`, `time-studies` to read from a replica).
2. **Async solver workers**: introduce Celery + Redis. `POST /api/balance/run`
   enqueues a job, returns `202 + run_id`; the frontend polls
   `GET /api/balance/runs/{id}` until status flips from `DRAFT` →
   `PROPOSED`.
3. **Per-tenant database**: if you go multi-factory, prefer a database-
   per-factory over a `factory_id` column on every row. The OR-Tools
   solver is already self-contained per request, so no shared state to
   untangle.
4. **Edge caching**: dashboard responses can be cached for 10 s at the
   edge (Cloudflare) since they auto-refresh every 30 s anyway.
5. **Sticky sessions for IoT**: if you horizontally scale the backend,
   pin each sensor's MQTT-bridge connection to one pod via a
   consistent-hash load balancer to keep the auto-status-flip logic
   predictable.

---

## Cheat sheet — one-screen production deploy (Path A)

```bash
# 1. Server setup (Ubuntu 24.04)
curl -fsSL https://get.docker.com | sh

# 2. Pull, configure, start
git clone <repo> /opt/lb && cd /opt/lb
cp .env.example .env && $EDITOR .env       # set JWT_SECRET, ANTHROPIC_API_KEY
docker compose up -d --build

# 3. Add Caddy (HTTPS) — see Path A.4
echo "lb.factory.com { reverse_proxy /api/* backend:8000 ; reverse_proxy frontend:80 }" > Caddyfile
docker compose up -d caddy

# 4. First-login hardening
curl -X POST http://localhost:8000/api/auth/login -d '{"username":"admin","password":"admin123"}' -H 'Content-Type: application/json'
# -> grab token, then POST /api/auth/users to create real users; disable defaults

# 5. Backups
echo '0 2 * * * docker exec lb-db-1 pg_dump -U postgres line_balancing | gzip > /backups/lb-$(date +\%F).sql.gz' | sudo crontab -
```
