"""Verify machines.last_maintenance_at create/update via the API."""
from __future__ import annotations


def test_create_with_maintenance_date(client, seed, auth_headers_pm):
    r = client.post(
        "/api/machines",
        headers=auth_headers_pm,
        json={
            "machine_code": "TEST-MAINT-1",
            "type": "SNLS",
            "line_id": seed["line"].id,
            "status": "IDLE",
            "last_maintenance_at": "2026-04-01T00:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["last_maintenance_at"] is not None
    assert body["last_maintenance_at"].startswith("2026-04-01")


def test_update_maintenance_date(client, seed, auth_headers_pm):
    # use an existing seeded machine
    machine = seed["machines"][0]
    r = client.put(
        f"/api/machines/{machine.id}",
        headers=auth_headers_pm,
        json={"last_maintenance_at": "2026-05-06T12:00:00Z"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["last_maintenance_at"].startswith("2026-05-06")


def test_clear_maintenance_date(client, seed, auth_headers_pm):
    machine = seed["machines"][0]
    # First set a value
    client.put(
        f"/api/machines/{machine.id}",
        headers=auth_headers_pm,
        json={"last_maintenance_at": "2026-04-01T00:00:00Z"},
    )
    # Then clear it
    r = client.put(
        f"/api/machines/{machine.id}",
        headers=auth_headers_pm,
        json={"last_maintenance_at": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["last_maintenance_at"] is None


def test_list_machines_includes_maintenance(client, seed, auth_headers_pm):
    r = client.get("/api/machines", headers=auth_headers_pm)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    # All rows must include the new field, even if null
    assert all("last_maintenance_at" in row for row in rows)
