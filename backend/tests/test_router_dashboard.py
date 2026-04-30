"""Router-level tests for the bottleneck dashboard."""
from __future__ import annotations


def test_bottleneck_no_run(client, seed, auth_headers_pm):
    r = client.get(
        f"/api/dashboard/bottleneck?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] is None
    assert body["heat"] == []
    assert body["wip_alerts"] == []
    assert body["root_causes"] == []


def test_bottleneck_with_run(client, seed, auth_headers_pm, applied_run):
    r = client.get(
        f"/api/dashboard/bottleneck?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == applied_run
    assert body["line_efficiency"] is not None
    assert len(body["heat"]) >= 1
    # Exactly one bottleneck flagged
    assert sum(1 for h in body["heat"] if h["is_bottleneck"]) == 1


def test_wip_alert_appears_on_dashboard(client, seed, auth_headers_pm, applied_run):
    # Push a WIP > threshold for station 1
    r = client.post(
        "/api/production/wip",
        headers=auth_headers_pm,
        json={"run_id": applied_run, "station": 1, "wip_units": 40, "threshold": 25},
    )
    assert r.status_code == 201

    body = client.get(
        f"/api/dashboard/bottleneck?line_id={seed['line'].id}",
        headers=auth_headers_pm,
    ).json()

    alerts = body["wip_alerts"]
    assert any(a["station"] == 1 and a["wip_units"] == 40 for a in alerts)
    # 40/25 = 1.6 -> critical (>=1.5x)
    crit = next(a for a in alerts if a["station"] == 1)
    assert crit["severity"] == "critical"

    heat_st1 = next(h for h in body["heat"] if h["station"] == 1)
    assert heat_st1["wip_units"] == 40
    assert heat_st1["wip_threshold"] == 25
