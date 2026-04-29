"""Idempotent seed: creates admin user, demo line, polo style with 35 ops,
machines, and 25 operators with a skill matrix.

Runs automatically on startup if the DB is empty.
"""
from __future__ import annotations

import random

from ..database import SessionLocal
from ..models import (
    User, UserRole, Line, Machine, MachineType, MachineStatus,
    Operator, OperatorSkill, AttendanceStatus,
    Style, Operation, OperationPrecedence,
)
from ..auth.security import hash_password
from .polo_shirt import POLO_SHIRT_OPERATIONS, POLO_SHIRT_PRECEDENCE


DEFAULT_ADMIN = {
    "username": "admin",
    "email": "admin@factory.local",
    "password": "admin123",
    "full_name": "Factory Admin",
    "role": UserRole.ADMIN,
}

DEMO_USERS = [
    {"username": "ie1", "email": "ie1@factory.local", "password": "ie123", "full_name": "Priya IE", "role": UserRole.IE},
    {"username": "sup1", "email": "sup1@factory.local", "password": "sup123", "full_name": "Ravi Supervisor", "role": UserRole.SUPERVISOR},
    {"username": "pm1", "email": "pm1@factory.local", "password": "pm123", "full_name": "Asha Manager", "role": UserRole.PRODUCTION_MANAGER},
]


def bootstrap_if_empty() -> None:
    db = SessionLocal()
    try:
        if db.query(User).first():
            return  # already seeded

        # 1. Users
        for u in [DEFAULT_ADMIN, *DEMO_USERS]:
            db.add(User(
                username=u["username"], email=u["email"],
                password_hash=hash_password(u["password"]),
                full_name=u["full_name"], role=u["role"],
            ))

        # 2. Lines
        line1 = Line(code="L1", name="Line 1 — Knit", capacity=30, working_minutes=480)
        line2 = Line(code="L2", name="Line 2 — Woven", capacity=25, working_minutes=480)
        db.add_all([line1, line2])
        db.flush()

        # 3. Machines (enough for the polo SAM mix)
        machine_specs = [
            ("SNLS", 18), ("OL", 8), ("FOA", 4),
            ("BARTACK", 2), ("BUTTON", 2), ("BUTTONHOLE", 2),
            ("IRON", 2), ("MANUAL", 4),
        ]
        for mtype, count in machine_specs:
            for i in range(1, count + 1):
                db.add(Machine(
                    machine_code=f"{mtype}-{i:03d}",
                    type=MachineType(mtype),
                    line_id=line1.id,
                    status=MachineStatus.IDLE,
                ))
        db.flush()

        # 4. Polo style + operations
        polo = Style(
            style_code="POLO-001",
            name="Basic Pique Polo Shirt",
            garment_type="Polo / Knit",
            description="Short-sleeve pique polo with 3-button placket and ribbed collar.",
        )
        db.add(polo)
        db.flush()

        op_by_code: dict[str, Operation] = {}
        for spec in POLO_SHIRT_OPERATIONS:
            o = Operation(
                style_id=polo.id,
                op_code=spec["op_code"],
                sequence=spec["sequence"],
                description=spec["description"],
                sam=spec["sam"],
                machine_type=MachineType(spec["machine_type"]),
                skill_level=spec["skill_level"],
                section=spec["section"],
            )
            db.add(o)
            db.flush()
            op_by_code[o.op_code] = o

        for pred, succ in POLO_SHIRT_PRECEDENCE:
            if pred in op_by_code and succ in op_by_code:
                db.add(OperationPrecedence(
                    style_id=polo.id,
                    predecessor_id=op_by_code[pred].id,
                    successor_id=op_by_code[succ].id,
                ))

        polo.total_sam = sum(o.sam for o in op_by_code.values())

        # 5. Operators (25)
        rng = random.Random(42)
        ops_list = list(op_by_code.values())
        names = [
            "Asha", "Bina", "Chitra", "Deepa", "Esha", "Farah", "Gita", "Hema",
            "Indu", "Jaya", "Kala", "Lata", "Mala", "Nita", "Omana", "Pooja",
            "Rani", "Sita", "Tara", "Uma", "Vidya", "Wahida", "Xita", "Yamuna", "Zara",
        ]
        for i, n in enumerate(names, start=1):
            grade = rng.choice([1, 2, 2, 3, 3, 4, 4, 5])
            base_eff = float(rng.randint(70, 110))
            opr = Operator(
                employee_code=f"EMP{i:04d}",
                name=n,
                grade=grade,
                base_efficiency=base_eff,
                attendance_status=AttendanceStatus.PRESENT,
                current_line_id=line1.id,
            )
            db.add(opr)
            db.flush()

            # Skill matrix: each operator certified on a subset weighted by skill_level
            for op in ops_list:
                if op.skill_level <= grade and rng.random() < 0.55:
                    eff = max(40, min(130, int(rng.gauss(base_eff, 10))))
                    db.add(OperatorSkill(
                        operator_id=opr.id, operation_id=op.id,
                        efficiency=float(eff), is_certified=True,
                    ))
            # Guarantee each op has at least 2 operators by another pass below
        db.flush()

        # Coverage pass: each op needs ≥2 operators certified
        for op in ops_list:
            count = db.query(OperatorSkill).filter(OperatorSkill.operation_id == op.id).count()
            if count < 2:
                eligible = db.query(Operator).filter(Operator.grade >= op.skill_level).all()
                rng.shuffle(eligible)
                for opr in eligible[: max(0, 2 - count)]:
                    if not db.query(OperatorSkill).filter(
                        OperatorSkill.operator_id == opr.id,
                        OperatorSkill.operation_id == op.id,
                    ).first():
                        db.add(OperatorSkill(
                            operator_id=opr.id, operation_id=op.id,
                            efficiency=float(rng.randint(70, 100)), is_certified=True,
                        ))

        db.commit()
    finally:
        db.close()
