"""Suggestion engine: pure math + HTTP route tests."""
from __future__ import annotations

import pytest

from app.services.suggestion import SuggestionInput, suggest


# ---------- pure-math tests ----------------------------------------
def test_basic_formula():
    """N=20, eff=80%, total_sam=16 -> 60 pieces/hr."""
    res = suggest(SuggestionInput(total_sam_min=16.0, operators=20, efficiency_pct=80.0))
    assert res.suggested_output_hour == 60
    # Per 480-min shift -> 480/hr-ish
    assert res.suggested_output_day == 60 * 8


def test_efficiency_changes_output():
    """Output scales linearly with efficiency."""
    a = suggest(SuggestionInput(total_sam_min=10.0, operators=10, efficiency_pct=50.0))
    b = suggest(SuggestionInput(total_sam_min=10.0, operators=10, efficiency_pct=100.0))
    assert b.suggested_output_hour == 2 * a.suggested_output_hour


def test_bottleneck_caps_output():
    """Heaviest op = 1 min -> ceiling 60/hr regardless of staffing."""
    res = suggest(SuggestionInput(
        total_sam_min=5.0, operators=100, efficiency_pct=100.0,
        bottleneck_op_min=1.0, bottleneck_op_code="OP_HARD",
    ))
    # Without the cap: (100*60*1.0)/5 = 1200/hr; with cap: <= 60
    assert res.suggested_output_hour == 60
    assert any("Capped by the bottleneck" in n for n in res.notes)


def test_reverse_operators_required():
    """At target, theoretical_operators_at_target should make sense."""
    res = suggest(SuggestionInput(
        total_sam_min=20.0, operators=10, efficiency_pct=80.0,
        target_output_hour=50,
    ))
    # 50 * 20 / (0.8 * 60) = 1000/48 ≈ 20.83 -> ceil 21
    assert res.theoretical_operators_at_target == 21
    assert any("21" in n for n in res.notes)


def test_zero_sam_returns_zero():
    res = suggest(SuggestionInput(total_sam_min=0.0, operators=10, efficiency_pct=80.0))
    assert res.suggested_output_hour == 0
    assert "no operations" in res.notes[0].lower()


# ---------- HTTP route tests ---------------------------------------
def test_suggest_endpoint_uses_line_capacity_default(client, seed, auth_headers_pm):
    r = client.post(
        "/api/balance/suggest",
        headers=auth_headers_pm,
        json={
            "style_id": seed["style"].id,
            "line_id": seed["line"].id,
            "efficiency_pct": 80,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Seeded line.capacity is 10 (see conftest)
    assert body["operators_used"] == 10
    assert body["efficiency_pct"] == 80
    assert body["suggested_output_hour"] >= 1
    assert body["bottleneck_op_code"] == "OP3"   # heaviest op (0.7 min) in seed
    assert isinstance(body["notes"], list) and len(body["notes"]) >= 1


def test_suggest_endpoint_explicit_operators(client, seed, auth_headers_pm):
    r = client.post(
        "/api/balance/suggest",
        headers=auth_headers_pm,
        json={
            "style_id": seed["style"].id,
            "line_id": seed["line"].id,
            "operators": 5,
            "efficiency_pct": 100,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["operators_used"] == 5
    # Total SAM = 0.5+0.6+0.7+0.4 = 2.2 min
    # output = 5 * 60 * 1.0 / 2.2 = ~136, but capped by OP3 (0.7 min) -> 85/hr
    assert body["suggested_output_hour"] <= int(60 / 0.7) + 1
    assert any("OP3" in n for n in body["notes"])


def test_suggest_endpoint_with_target_hour(client, seed, auth_headers_pm):
    r = client.post(
        "/api/balance/suggest",
        headers=auth_headers_pm,
        json={
            "style_id": seed["style"].id,
            "line_id": seed["line"].id,
            "operators": 4,
            "efficiency_pct": 80,
            "target_output_hour": 100,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["theoretical_operators_at_target"] is not None
    assert body["theoretical_operators_at_target"] >= 1


def test_suggest_endpoint_unknown_style(client, seed, auth_headers_pm):
    r = client.post(
        "/api/balance/suggest",
        headers=auth_headers_pm,
        json={"style_id": 99999, "line_id": seed["line"].id},
    )
    assert r.status_code == 404
