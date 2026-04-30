"""Router-level tests for the real-time re-balance flow."""
from __future__ import annotations

from app.models import AttendanceStatus, MachineStatus


# ---------- /check ----------------------------------------------------
def test_check_no_triggers(client, seed, auth_headers_pm, applied_run):
    r = client.get(
        f"/api/rebalance/check?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["triggered"] is False
    assert body["trigger"] is None


def test_check_operator_absent(db, client, seed, auth_headers_pm, applied_run):
    # Mark Asha (assigned to the run) as ABSENT
    operator = seed["operators"][0]
    operator.attendance_status = AttendanceStatus.ABSENT
    db.merge(operator)
    db.commit()

    r = client.get(
        f"/api/rebalance/check?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    )
    body = r.json()
    assert body["triggered"] is True
    assert body["trigger"] == "OPERATOR_ABSENT"
    assert operator.id in body["absent_operator_ids"]


def test_check_machine_breakdown(db, client, seed, auth_headers_pm, applied_run):
    snls = next(m for m in seed["machines"] if m.type.value == "SNLS")
    snls.status = MachineStatus.BREAKDOWN
    db.merge(snls)
    db.commit()

    body = client.get(
        f"/api/rebalance/check?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    ).json()
    assert body["triggered"] is True
    # Operator-absent takes priority if both are set; here only machine breakdown is.
    assert body["trigger"] == "MACHINE_BREAKDOWN"
    assert snls.id in body["broken_machine_ids"]


def test_check_output_deviation(client, seed, auth_headers_pm, applied_run):
    # Capture an hourly with 30/60 actual/target -> 50% deviation
    r = client.post(
        "/api/production/hourly",
        headers=auth_headers_pm,
        json={
            "line_id": seed["line"].id, "run_id": applied_run,
            "hour_slot": 1, "target": 60, "actual": 30,
        },
    )
    assert r.status_code == 201

    body = client.get(
        f"/api/rebalance/check?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    ).json()
    assert body["triggered"] is True
    assert body["trigger"] == "OUTPUT_DEVIATION"
    assert body["deviation_pct"] is not None and body["deviation_pct"] > 15


def test_check_within_tolerance_does_not_trigger(client, seed, auth_headers_pm, applied_run):
    r = client.post(
        "/api/production/hourly",
        headers=auth_headers_pm,
        json={
            "line_id": seed["line"].id, "run_id": applied_run,
            "hour_slot": 1, "target": 60, "actual": 55,  # ~8% deviation
        },
    )
    assert r.status_code == 201

    body = client.get(
        f"/api/rebalance/check?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    ).json()
    assert body["triggered"] is False


# ---------- /propose & /decide ---------------------------------------
def test_propose_creates_event_and_diff(client, seed, auth_headers_pm, applied_run):
    r = client.post(
        "/api/rebalance/propose",
        headers=auth_headers_pm,
        json={"line_id": seed["line"].id, "trigger": "MANUAL"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["previous_run_id"] == applied_run
    assert body["new_run_id"] != applied_run
    assert body["event_id"] > 0
    assert isinstance(body["diffs"], list) and len(body["diffs"]) >= 1
    # Each diff entry has both before and after fields
    sample = body["diffs"][0]
    for k in ("station", "operator_before", "operator_after",
              "op_codes_before", "op_codes_after",
              "load_pct_before", "load_pct_after"):
        assert k in sample


def test_decide_accept_promotes_new_run(db, client, seed, auth_headers_pm, applied_run):
    propose = client.post(
        "/api/rebalance/propose",
        headers=auth_headers_pm,
        json={"line_id": seed["line"].id, "trigger": "MANUAL"},
    ).json()
    event_id = propose["event_id"]
    new_run_id = propose["new_run_id"]

    r = client.post(
        f"/api/rebalance/events/{event_id}/decide",
        headers=auth_headers_pm,
        json={"accepted": True},
    )
    assert r.status_code == 200, r.text

    # Re-fetch through the API to make sure status flipped
    from app.models import BalanceRun, BalanceStatus
    db.expire_all()
    new_run = db.get(BalanceRun, new_run_id)
    prev_run = db.get(BalanceRun, applied_run)
    assert new_run.status == BalanceStatus.APPLIED
    assert prev_run.status == BalanceStatus.REJECTED


def test_decide_reject_does_not_change_runs(db, client, seed, auth_headers_pm, applied_run):
    propose = client.post(
        "/api/rebalance/propose",
        headers=auth_headers_pm,
        json={"line_id": seed["line"].id, "trigger": "MANUAL"},
    ).json()

    r = client.post(
        f"/api/rebalance/events/{propose['event_id']}/decide",
        headers=auth_headers_pm,
        json={"accepted": False},
    )
    assert r.status_code == 200, r.text

    from app.models import BalanceRun, BalanceStatus
    db.expire_all()
    prev_run = db.get(BalanceRun, applied_run)
    assert prev_run.status == BalanceStatus.APPLIED


def test_events_listing(client, seed, auth_headers_pm, applied_run):
    client.post(
        "/api/rebalance/propose",
        headers=auth_headers_pm,
        json={"line_id": seed["line"].id, "trigger": "MANUAL"},
    )
    r = client.get(
        f"/api/rebalance/events?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    )
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and len(rows) >= 1
    assert rows[0]["line_id"] == seed["line"].id
