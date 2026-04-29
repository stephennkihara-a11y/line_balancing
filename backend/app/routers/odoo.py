"""Odoo 18 integration surface.

We expose a small REST API that mirrors Odoo's `search_read` / `create` /
`write` semantics so a thin Odoo connector module on the ERP side can sync
operators, work-centers (machines), routings (operations) and balancing
runs (production orders).

Models exposed (alias -> local source):
  - lb.style              -> styles
  - lb.operation          -> operations
  - lb.operator           -> operators (Odoo: hr.employee subset)
  - lb.machine            -> machines  (Odoo: mrp.workcenter)
  - lb.balance_run        -> balance_runs
  - lb.balance_assignment -> balance_assignments

External ID mapping is persisted in `erp_external_ids` so re-syncs are
idempotent.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth.security import require_role
from ..database import get_db
from ..models import (
    Style, Operation, Operator, Machine, BalanceRun, BalanceAssignment,
    ErpExternalId, User, UserRole,
)
from ..schemas.odoo import (
    OdooSearchReadRequest, OdooSearchReadResponse,
    OdooExternalIdMap, OdooExternalIdOut,
)

router = APIRouter(prefix="/api/odoo", tags=["odoo"])

MODEL_MAP: dict[str, type] = {
    "lb.style": Style,
    "lb.operation": Operation,
    "lb.operator": Operator,
    "lb.machine": Machine,
    "lb.balance_run": BalanceRun,
    "lb.balance_assignment": BalanceAssignment,
}


def _record_to_dict(row: Any, fields: list[str] | None) -> dict[str, Any]:
    cols = row.__table__.columns.keys()
    if fields:
        cols = [c for c in cols if c in fields]
    out: dict[str, Any] = {}
    for c in cols:
        v = getattr(row, c)
        # serialise enums and dates
        if hasattr(v, "value"):
            v = v.value
        elif hasattr(v, "isoformat"):
            v = v.isoformat()
        out[c] = v
    return out


def _apply_domain(query, model: type, domain: list[Any]):
    """Tiny subset of Odoo domain parsing: list of [field, op, value] triples.

    Supports ops: =, !=, in, not in, >, <, >=, <=, ilike.
    """
    cols = model.__table__.columns
    for triple in domain:
        if not isinstance(triple, (list, tuple)) or len(triple) != 3:
            continue
        field, op, value = triple
        col = cols.get(field)
        if col is None:
            continue
        if op == "=":
            query = query.filter(col == value)
        elif op == "!=":
            query = query.filter(col != value)
        elif op == "in":
            query = query.filter(col.in_(value))
        elif op == "not in":
            query = query.filter(~col.in_(value))
        elif op == ">":
            query = query.filter(col > value)
        elif op == "<":
            query = query.filter(col < value)
        elif op == ">=":
            query = query.filter(col >= value)
        elif op == "<=":
            query = query.filter(col <= value)
        elif op == "ilike":
            query = query.filter(col.ilike(f"%{value}%"))
    return query


@router.post("/search_read", response_model=OdooSearchReadResponse)
def search_read(
    payload: OdooSearchReadRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(
        UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.ADMIN, UserRole.SUPERVISOR,
    )),
) -> OdooSearchReadResponse:
    model = MODEL_MAP.get(payload.model)
    if not model:
        raise HTTPException(404, f"Unknown model {payload.model!r}. "
                                  f"Known: {sorted(MODEL_MAP)}")
    q = db.query(model)
    q = _apply_domain(q, model, payload.domain)
    rows = q.offset(payload.offset).limit(payload.limit).all()
    records = [_record_to_dict(r, payload.fields) for r in rows]
    return OdooSearchReadResponse(model=payload.model, length=len(records), records=records)


@router.post("/external-ids", response_model=OdooExternalIdOut, status_code=201)
def map_external_id(
    payload: OdooExternalIdMap,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.ADMIN)),
) -> ErpExternalId:
    existing = (
        db.query(ErpExternalId)
        .filter(
            ErpExternalId.entity == payload.entity,
            ErpExternalId.local_id == payload.local_id,
            ErpExternalId.erp_system == "odoo",
        )
        .first()
    )
    if existing:
        existing.erp_id = payload.erp_id
        existing.erp_model = payload.erp_model
        db.commit()
        db.refresh(existing)
        return existing

    rec = ErpExternalId(
        entity=payload.entity,
        local_id=payload.local_id,
        erp_system="odoo",
        erp_model=payload.erp_model,
        erp_id=payload.erp_id,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/external-ids", response_model=list[OdooExternalIdOut])
def list_external_ids(
    entity: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(
        UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.ADMIN, UserRole.SUPERVISOR,
    )),
) -> list[ErpExternalId]:
    q = db.query(ErpExternalId).filter(ErpExternalId.erp_system == "odoo")
    if entity:
        q = q.filter(ErpExternalId.entity == entity)
    return q.order_by(ErpExternalId.last_sync.desc()).limit(500).all()
