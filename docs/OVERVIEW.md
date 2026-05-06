# Apparel Line Balancing — Overview

## What this application is

A web-based, AI-assisted **line balancing system** for apparel
(cut-make-trim) factories. It replaces the spreadsheet that an Industrial
Engineer uses to plan how a sewing line is laid out — which operator
performs which operation, on which machine, in what order — and turns
that planning into a **continuous, data-driven loop** that adapts when
reality on the floor changes.

It is not just a balancer. It is a **closed-loop production-planning
tool** that:

1. Plans the line in seconds instead of half a day,
2. Watches the floor in real time and proposes re-balances when output
   deviates,
3. Diagnoses bottlenecks with concrete suggestions,
4. Captures floor data (time studies, IoT sensors, hourly output) that
   makes the next plan better,
5. Talks to the ERP (Odoo) so the office sees what the floor is doing.

## Who it is for

| Role                  | What they do in the system                                                                           |
|-----------------------|------------------------------------------------------------------------------------------------------|
| **Industrial Engineer (IE)**  | Maintain master data, run line balances for new styles, capture time studies, audit standard SAM.    |
| **Production Manager**| Monitor multiple lines, accept/reject re-balance proposals, review efficiency and balance-loss KPIs. |
| **Supervisor**        | Capture hourly production, log WIP, mark operators absent or machines broken, view the floor dashboard. |
| **Admin**             | Manage users and system configuration.                                                                |
| **Operator** (future) | View their station, log their own time studies on a tablet.                                           |

---

## What the application achieves (vs Excel-based status quo)

| Activity                              | Excel today                   | This system                           |
|---------------------------------------|-------------------------------|---------------------------------------|
| Balance a 35-op style                 | 4–8 hours of an IE's day      | **Seconds** (optimal CP-SAT solver)   |
| Re-balance when an operator is absent | Rarely done — line runs imbalanced | Auto-suggested, before/after diff, one click to apply |
| Find the bottleneck                   | Eyeball the spreadsheet       | **Heatmap + root-cause suggestion** (skill / machine / method / layout) |
| Capture cycle times on the floor      | Stopwatch + paper             | **Mobile time-study app** with rating/allowance and live SAM           |
| Compare captured vs standard SAM      | Quarterly sampling, by hand   | Live aggregate, flagged when ≥10% deviation                           |
| Track machine utilisation             | Not done                      | **Live IoT running %** per machine                                    |
| Push plan to ERP (Odoo)               | Manual data re-entry          | **Automatic 15-min sync** via the connector addon                     |
| Visibility across roles               | Files emailed around          | Real-time, role-aware web app + tablet PWA                            |
| Explain a layout to the team          | Whoever made the spreadsheet  | **Claude AI narrative** — bottleneck, cause, what to do               |

---

## Core processes (end-to-end factory loop)

```
   ┌─────────────────────────────────────────────────────────────────┐
   │                     PLAN  (Industrial Engineer)                 │
   │                                                                 │
   │   1. Master data: line / machines / operators / skills          │
   │   2. New style: import operation bulletin (CSV/XLSX)            │
   │   3. Balance Wizard: pick style + line + target/hr              │
   │      → CP-SAT solver returns operator-by-operator layout        │
   │      → Claude generates a narrative explanation                 │
   └────────────────────────────┬────────────────────────────────────┘
                                ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                    EXECUTE  (Supervisor + Operators)            │
   │                                                                 │
   │   4. Floor placed per the layout                                │
   │   5. Supervisor logs hourly production, WIP per station         │
   │   6. IoT sensors stream machine running/idle to /api/iot        │
   └────────────────────────────┬────────────────────────────────────┘
                                ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                    MONITOR  (Bottleneck Dashboard)              │
   │                                                                 │
   │   7. Heatmap shows station load (red >100% / amber / green)     │
   │   8. WIP alerts when a station exceeds its threshold            │
   │   9. Root-cause analysis points at:                             │
   │         • skill_gap   • machine   • method   • layout           │
   └────────────────────────────┬────────────────────────────────────┘
                                ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                   ADAPT  (Real-time re-balance)                 │
   │                                                                 │
   │   10. Trigger detected:                                          │
   │         • operator absent  • machine breakdown                   │
   │         • hourly output deviates > ±15%  • target changed        │
   │   11. /api/rebalance/propose → re-solves with current state      │
   │   12. Before/after diff shown; PM accepts → new run APPLIED      │
   └────────────────────────────┬────────────────────────────────────┘
                                ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                LEARN  (Time studies + ERP sync)                 │
   │                                                                 │
   │   13. IE captures cycle times on tablet → captured SAM updates   │
   │   14. Aggregate flags ops where method ≠ standard                │
   │   15. Odoo connector syncs styles, runs and operator data        │
   │       so the office sees factory state in MRP                    │
   └─────────────────────────────────────────────────────────────────┘
```

---

## Key processes in detail

### Process 1 — Plan a new style

**Goal**: Given a new garment style and the operators on a line today,
produce an operator-by-operator layout that minimises the bottleneck
cycle time and meets the daily output target.

**Steps**:

1. IE opens **Styles** → uploads the operation bulletin (a CSV with
   `op_code, sequence, description, sam, machine_type, skill_level,
   section, predecessors`). The system computes total SAM, validates
   precedence, and shows the routing as a list.
2. IE goes to **Balance Wizard**, picks the style, picks the line,
   types target output per hour (e.g. `60`), optionally hand-picks
   operators (default: every PRESENT operator on the line).
3. Click **Solve and view layout**. Behind the scenes:
   - The CP-SAT solver maximises line efficiency subject to:
     * each operation assigned to exactly one operator/station,
     * precedence (predecessor station ≤ successor station),
     * skill match (operator must be certified on the op),
     * machine availability (no more stations than machines per type),
     * one operator per station.
   - A Ranked Positional Weight (RPW) heuristic seeds the search so
     the solver finds a near-optimal layout in seconds, even on 35-op
     styles.
   - Claude generates a 200-word narrative: where the bottleneck is,
     what's causing it, what to consider doing.
4. The Result page shows takt, theoretical-vs-actual operators, line
   efficiency, balance loss, station heatmap, the operator-by-operator
   table, and the AI explanation. The IE can ask "what if we drop to
   12 operators?" in plain English.

**Achievement**: A balance that used to take 4–8 hours of spreadsheet
work is produced in under a minute, with quantified efficiency and
explainable trade-offs.

### Process 2 — Run the line and watch it

**Goal**: Keep the line running to plan; catch and fix issues before
the shift target is missed.

**Steps**:

1. Supervisor opens **Bottleneck Dashboard** and picks the line.
2. Every 30 seconds, the page refreshes:
   - Station heatmap (load %) with the bottleneck ringed in red,
   - WIP units per station (captured manually or via tablet form),
   - Last hour's actual vs target,
   - Root-cause card for the bottleneck.
3. At each hour boundary the supervisor types in the count produced.
   The system computes deviation and, if > ±15%, flags
   **OUTPUT_DEVIATION** as a re-balance trigger.
4. If an operator is marked **ABSENT** or a machine **BREAKDOWN**, the
   trigger banner appears immediately.

**Achievement**: The shop floor's state is visible to the office in
real time, with explicit, prioritised alerts instead of vague gut feel.

### Process 3 — Re-balance in response to reality

**Goal**: When something has changed (people, machines, demand,
performance), produce a new layout that respects the new constraints —
and let a human decide whether to apply it.

**Steps**:

1. The trigger banner offers **Propose new balance**.
2. Behind the scenes, the solver runs again with:
   - Current PRESENT operators (absent ones excluded),
   - Current WORKING/IDLE machines (broken ones excluded),
   - The same style and target (or a new target if the IE changed it).
3. The system persists a new run + a `rebalance_event` linking the two
   runs and showing:
   - Eff before vs after,
   - Δ output per hour,
   - Station-by-station diff: which operators moved, which ops moved.
4. Production Manager reviews the diff and clicks **Accept** or
   **Reject**.
   - **Accept** → previous run becomes `REJECTED`, new run becomes
     `APPLIED` and is what the dashboard now reflects.
   - **Reject** → previous run stays `APPLIED`, the proposal is logged
     for audit but not used.

**Achievement**: Re-balancing — which is normally never done because
nobody has time — happens fluidly, with full audit trail and human
final say. Lines stay efficient even when reality drifts.

### Process 4 — Diagnose the bottleneck

**Goal**: Don't just say "station 7 is slow" — say *why* and *what to
do*.

**Steps**:

The dashboard's root-cause analysis combines four signals:

| Cause       | Detection rule                                                                                  | Suggestion                                                |
|-------------|--------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| `skill_gap` | Operator's efficiency on the bottleneck op is ≥ 8 points below the average across all certified operators | Swap with the fastest available operator, or cross-train |
| `machine`   | One or more machines of the bottleneck-op type are in BREAKDOWN                                  | Recover machines or reroute the op                        |
| `method`    | Captured time-study SAM averages ≥ 10% above the standard                                        | Re-run the method study; check workplace layout / motion economy |
| `layout`    | Total SAM at the station > 110% of takt                                                          | Split the station; move one op to a new station           |

**Achievement**: An IE who arrives at the line gets a root-cause
shortlist instead of having to diagnose from scratch, dramatically
shortening the time from "we missed target" to "we know what to fix".

### Process 5 — Capture better data over time

**Goal**: Make every balance more accurate than the last by collecting
real cycle times and machine utilisation from the floor.

**Steps**:

- **Time studies** (mobile-friendly): IE opens the Time Study page on
  a tablet, picks the operation, and uses the built-in stopwatch
  (Start / Lap / Stop) to capture multiple samples. Rating and
  allowance are typed in; the system computes captured SAM and shows
  it next to the standard. A style-level aggregate flags any operation
  whose captured average deviates ≥ 10% from standard — that flag
  feeds the `method` root cause above.
- **IoT telemetry**: each sewing machine equipped with a sensor sends
  batches of `{is_running, rpm}` events to `/api/iot/telemetry`. The
  utilisation page shows per-machine running % over the last 60
  minutes, and the system auto-flips a machine's status from IDLE to
  WORKING (and vice versa) on each sensor event.

**Achievement**: The factory's "standard" gets continuously
re-validated against reality. Stale SAM values that quietly drag down
efficiency become visible.

### Process 6 — Push and pull from Odoo (ERP)

**Goal**: Keep the office's MRP in sync with what the floor is doing,
without anyone re-typing data.

**Steps**:

1. The Odoo addon (`odoo/line_balancing_connector/`) is installed in
   the factory's existing Odoo 18 server.
2. An admin enters the FastAPI base URL and a service-account
   username/password in **Manufacturing → Line Balancing → Settings**.
3. Every 15 minutes, a cron triggers `lb.sync.sync_all()`:
   - Pulls styles + operations into `lb.style` / `lb.operation`,
   - Pulls operators into `lb.operator` (each linkable to
     `hr.employee`),
   - Pulls machines into `lb.machine` (each linkable to
     `mrp.workcenter`),
   - Pulls balance runs + assignments into `lb.balance.run` /
     `lb.balance.assignment` (each linkable to `mrp.production`),
   - Pushes Odoo's IDs back to the FastAPI's `/api/odoo/external-ids`
     so future reports can quote Odoo's identifiers.

**Achievement**: The office sees the factory's actual line
configuration inside their ERP without anyone re-keying data — the
single biggest source of error in traditional factories.

---

## What the system delivers as outputs

Per balance run, the system stores:
- The full station-by-station layout (operator + ops + machine),
- Takt time, theoretical operator count, line efficiency, balance loss,
- The bottleneck station and its cause(s),
- A natural-language explanation suitable for a supervisor briefing.

Per shift, the system stores:
- Hourly production target vs actual,
- WIP per station over time,
- Re-balance events with before/after deltas,
- Operator attendance changes,
- Machine status changes (manual + auto from IoT).

Per operation:
- Captured time-study samples vs standard SAM,
- Per-operator efficiency on that op (for the skill matrix),
- Method-deviation flag.

These can be exported (Phase 1 has CSV/XLSX import; PDF/Excel report
export is on the roadmap) or pulled by Odoo for finance / payroll /
delivery-date calculations.

---

## What this does not do (yet)

Honest scope boundaries so expectations match reality:

- It does not run the sewing machines — it tells operators where to
  stand and what to do; physical movement is human.
- It does not auto-decide: every re-balance proposal needs a human
  Accept. By design, the system suggests; the production manager
  decides.
- It does not include payroll/incentive calculation — but the
  efficiency and per-operator output data needed for that are present
  and queryable.
- Phase 1 reporting is dashboard-only; PDF/Excel export and
  per-operator scorecards are planned but not yet shipped.

---

## How users typically experience it on day one

A realistic first-week walkthrough:

1. **Day 1 (IE)**: Import existing operation bulletin for one style,
   import the operator skill matrix, run a balance. Compare the
   AI-produced layout to what the line is currently running. Adjust
   skill efficiencies where the captured cycle times disagree.
2. **Day 2 (Supervisor)**: Capture hourly counts on the existing
   layout. The dashboard shows balance loss and the bottleneck.
3. **Day 3 (PM)**: Accept the proposed re-balance from day 1.
   Re-run for the next day's target. Output goes up by 5–15%.
4. **Day 5 (IE)**: Capture time studies on the bottleneck operation;
   the captured SAM vs standard deviation reveals a method issue not
   the skill issue everyone assumed. Method study fixes it.
5. **End of week 1**: Repeat across two more styles. The factory now
   has a continuously-running plan-monitor-adapt loop where it used to
   have a once-a-month spreadsheet exercise.

The system pays for itself in the line efficiency improvement — even
a 5% lift on a 25-operator line typically funds the rollout in under
two months.
