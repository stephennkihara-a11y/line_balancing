# Line Balancing — Odoo 18 Connector

A small Odoo 18 addon that pulls Styles, Operations, Operators, Machines and
Balance Runs from the Apparel Line Balancing FastAPI service into local
mirror tables, and pushes Odoo's IDs back so the API can quote them.

## Install

1. Copy this directory into one of Odoo's `addons_path` folders, e.g.:
   ```bash
   cp -r odoo/line_balancing_connector /opt/odoo/custom-addons/
   ```
2. Restart Odoo with that path enabled:
   ```bash
   odoo -d <db> --addons-path=/opt/odoo/addons,/opt/odoo/custom-addons -u line_balancing_connector
   ```
3. In Odoo, go to **Apps**, click **Update Apps List**, then install
   **Line Balancing Connector**.

## Configure

Manufacturing → Line Balancing → Settings → create one record:

| Field        | Example                              |
|--------------|--------------------------------------|
| `base_url`   | `http://line-balancing.internal:8000`|
| `username`   | `admin`                              |
| `password`   | `admin123`                           |
| `enabled`    | ✓                                    |

Toggle the four `sync_*` flags as needed.

## How it works

```
            ┌────────────────────────────────────────┐
            │            FastAPI service             │
            │  /api/odoo/search_read     (Phase 3)   │
            │  /api/odoo/external-ids               │
            │  /api/balance/runs/...                │
            └────────────────┬───────────────────────┘
                             │ HTTPS + JWT
            ┌────────────────▼───────────────────────┐
            │  lb.client (REST helper)               │
            │     login() → access_token             │
            │     search_read(model, domain, …)      │
            │     upsert_external_id(...)            │
            └────────────────┬───────────────────────┘
                             │
            ┌────────────────▼───────────────────────┐
            │  lb.sync.sync_all()                    │
            │     • styles + operations              │
            │     • operators (link to hr.employee)  │
            │     • machines (link to mrp.workcenter)│
            │     • balance runs + assignments       │
            └────────────────┬───────────────────────┘
                             │ writes
                  lb.style / lb.operation / lb.operator
                  lb.machine / lb.balance.run
                  lb.balance.assignment
```

A cron job (`data/ir_cron.xml`) runs `model.sync_all()` every 15 minutes.
You can also run it interactively from **Manufacturing → Sync now**.

## Linking to Odoo MRP

Each mirror model carries a Many2one to the matching MRP record so a
production manager can connect them once:

| Mirror model       | Links to                        |
|--------------------|---------------------------------|
| `lb.machine`       | `mrp.workcenter`                |
| `lb.operation`     | `mrp.routing.workcenter`        |
| `lb.operator`      | `hr.employee`                   |
| `lb.balance.run`   | `mrp.production`                |

These links are not auto-populated — the connector deliberately leaves
the matching to the user / a custom matching rule.

## API endpoints used

| Endpoint                              | Purpose                               |
|---------------------------------------|---------------------------------------|
| `POST /api/auth/login`                | Obtain JWT                            |
| `POST /api/odoo/search_read`          | Pull master data + balance runs       |
| `POST /api/odoo/external-ids`         | Push Odoo IDs back to the API         |
| `GET  /api/balance/runs`              | List recent runs                      |
| `GET  /api/balance/runs/{id}`         | Pull full assignment list             |

## Extending

- Push hourly production / WIP back to the API: add a method that calls
  `POST /api/production/hourly` from inside an MRP work-order
  state-change hook.
- Listen to MRP machine breakdowns: when an `mrp.workcenter`'s working
  state flips to broken, propagate to the linked `lb.machine` and
  `POST /api/rebalance/check` to surface a re-balance proposal back in
  Odoo.
- Time studies from the shop floor: extend `mrp.workorder` to include
  cycle-time entry that posts to `POST /api/time-studies`.
