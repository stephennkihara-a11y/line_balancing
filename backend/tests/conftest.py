"""Pytest fixtures: in-memory SQLite, FastAPI test client, seeded data.

The fixtures wire up an in-memory SQLite engine, override the FastAPI
`get_db` dependency, build all tables via `Base.metadata.create_all`
(equivalent to running `alembic upgrade head` against a fresh DB), and
seed the minimum master data needed by the dashboard / rebalance tests:
a line, a style with 4 ops + precedence, three operators with skill
matrices, and a pool of machines.
"""
from __future__ import annotations

import os

# Force a fresh in-memory SQLite before any app modules read settings.
os.environ.setdefault("DATABASE_URL", "sqlite:///file:lb_test?mode=memory&cache=shared&uri=true")
os.environ.setdefault("JWT_SECRET", "test-secret-please-change-in-prod-32chars!!")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Patch the engine before app.main imports it
from app import database as db_mod
from app.database import Base


# ----- Engine ----------------------------------------------------------
TEST_URL = os.environ["DATABASE_URL"]
engine = create_engine(
    TEST_URL,
    connect_args={"check_same_thread": False, "uri": True},
)


@event.listens_for(engine, "connect")
def _enable_fk(dbapi_conn, _conn_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Replace the app's engine + sessionmaker with the test ones BEFORE main loads
db_mod.engine = engine
db_mod.SessionLocal = TestingSessionLocal


# ----- Helpers --------------------------------------------------------
def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def app():
    """Build the FastAPI app once, with migrations skipped (we use create_all)."""
    # Avoid alembic at startup — the testing engine isn't reachable through
    # the normal config. Patch run_migrations to a no-op and skip seed
    # bootstrap (we'll seed our own data per test).
    from app import db_migrations
    db_migrations.run_migrations = lambda: None  # type: ignore[assignment]

    from app.main import create_app
    from app.database import get_db

    Base.metadata.create_all(bind=engine)

    application = create_app()
    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest.fixture
def db():
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


# ----- Seed -----------------------------------------------------------
@pytest.fixture
def seed(db):
    """Create a minimal world for tests: 1 line, 1 style, 4 ops, 3 ops + machines."""
    from app.auth.security import hash_password
    from app.models import (
        User, UserRole, Line, Machine, MachineType, MachineStatus,
        Operator, OperatorSkill, AttendanceStatus,
        Style, Operation, OperationPrecedence,
        BalanceRun, BalanceAssignment, BalanceStatus,
    )

    # Wipe any prior state
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()

    admin = User(
        username="admin",
        email="admin@test.local",
        password_hash=hash_password("admin"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
    )
    pm = User(
        username="pm",
        email="pm@test.local",
        password_hash=hash_password("pm"),
        full_name="PM",
        role=UserRole.PRODUCTION_MANAGER,
    )
    db.add_all([admin, pm])

    line = Line(code="L1", name="Line 1", capacity=10, working_minutes=480)
    db.add(line)
    db.flush()

    # 6 SNLS, 2 OL, 2 BARTACK, 2 MANUAL
    machines = []
    for t, n in [("SNLS", 6), ("OL", 2), ("BARTACK", 2), ("MANUAL", 2)]:
        for i in range(1, n + 1):
            m = Machine(
                machine_code=f"{t}-{i:02d}",
                type=MachineType(t),
                line_id=line.id,
                status=MachineStatus.IDLE,
            )
            db.add(m)
            machines.append(m)
    db.flush()

    style = Style(
        style_code="TST-001",
        name="Test Style",
        garment_type="Test",
    )
    db.add(style)
    db.flush()

    op_specs = [
        ("OP1", 1, "Op one",   0.5, "SNLS", 1),
        ("OP2", 2, "Op two",   0.6, "SNLS", 2),
        ("OP3", 3, "Op three", 0.7, "OL",   2),
        ("OP4", 4, "Op four",  0.4, "MANUAL", 1),
    ]
    ops_by_code = {}
    for code, seq, desc, sam, mt, sk in op_specs:
        o = Operation(
            style_id=style.id, op_code=code, sequence=seq, description=desc,
            sam=sam, machine_type=MachineType(mt), skill_level=sk,
        )
        db.add(o)
        db.flush()
        ops_by_code[code] = o

    style.total_sam = sum(spec[3] for spec in op_specs)

    # Linear precedence
    for a, b in [("OP1", "OP2"), ("OP2", "OP3"), ("OP3", "OP4")]:
        db.add(OperationPrecedence(
            style_id=style.id,
            predecessor_id=ops_by_code[a].id,
            successor_id=ops_by_code[b].id,
        ))

    # Three operators on this line
    operators_data = [
        ("E001", "Asha",  3, 100.0),
        ("E002", "Bina",  3,  90.0),
        ("E003", "Chitra", 3, 110.0),
    ]
    operators = []
    for code, name, grade, eff in operators_data:
        o = Operator(
            employee_code=code, name=name, grade=grade, base_efficiency=eff,
            attendance_status=AttendanceStatus.PRESENT, current_line_id=line.id,
        )
        db.add(o)
        db.flush()
        operators.append(o)

    # Skill matrix: each operator certified on every op (varying efficiency)
    eff_grid = [
        # OP1, OP2, OP3, OP4
        [100, 100, 100, 100],   # Asha
        [ 70,  85,  95,  80],   # Bina  (slow on OP1 -> creates a clear skill_gap)
        [110, 105, 100, 100],   # Chitra
    ]
    for opr_idx, opr in enumerate(operators):
        for op_idx, code in enumerate(["OP1", "OP2", "OP3", "OP4"]):
            db.add(OperatorSkill(
                operator_id=opr.id,
                operation_id=ops_by_code[code].id,
                efficiency=eff_grid[opr_idx][op_idx],
                is_certified=True,
            ))
    db.commit()

    return {
        "admin": admin, "pm": pm,
        "line": line, "style": style,
        "ops": ops_by_code, "operators": operators, "machines": machines,
    }


@pytest.fixture
def auth_headers_pm(client, seed) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": "pm", "password": "pm"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth_headers_admin(client, seed) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def applied_run(client, seed, auth_headers_pm) -> int:
    """Solve a balance run for the seeded style/line and mark it APPLIED."""
    r = client.post(
        "/api/balance/run",
        headers=auth_headers_pm,
        json={
            "style_id": seed["style"].id,
            "line_id": seed["line"].id,
            "target_output_hour": 60,
            "explain": False,
        },
    )
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]

    apply = client.post(f"/api/balance/runs/{run_id}/apply", headers=auth_headers_pm)
    assert apply.status_code == 200, apply.text
    return run_id
