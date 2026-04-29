"""CSV/Excel import for operation bulletins.

POST /api/imports/operation-bulletin/{style_id}
Accepts a multipart upload of CSV or XLSX with columns:
    op_code, sequence, description, sam, machine_type, skill_level, section, predecessors

`predecessors` is a comma-separated list of op_codes already in the file.
"""
from __future__ import annotations

import io
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Style, Operation, OperationPrecedence, MachineType, User, UserRole
from ..auth.security import require_role
from ..schemas.style import StyleDetail

router = APIRouter(prefix="/api/imports", tags=["imports"])


REQUIRED = ["op_code", "sequence", "description", "sam", "machine_type"]


def _read_table(file: UploadFile, content: bytes) -> pd.DataFrame:
    name = (file.filename or "").lower()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(content))
    # try CSV by default
    return pd.read_csv(io.BytesIO(content))


@router.post("/operation-bulletin/{style_id}", response_model=StyleDetail)
async def import_bulletin(
    style_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE)),
):
    style = db.query(Style).options(selectinload(Style.operations)).filter(Style.id == style_id).first()
    if not style:
        raise HTTPException(404, "Style not found")

    content = await file.read()
    try:
        df = _read_table(file, content)
    except Exception as e:
        raise HTTPException(400, f"Could not parse file: {e}")

    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")

    # Replace existing operations
    for op in list(style.operations):
        db.delete(op)
    db.flush()

    op_by_code: dict[str, Operation] = {}
    rows: list[dict[str, Any]] = df.to_dict(orient="records")
    for r in rows:
        try:
            mt = MachineType(str(r["machine_type"]).strip().upper())
        except ValueError:
            raise HTTPException(400, f"Unknown machine_type {r['machine_type']!r} for op {r.get('op_code')}")
        op = Operation(
            style_id=style.id,
            op_code=str(r["op_code"]).strip(),
            sequence=int(r["sequence"]),
            description=str(r["description"]).strip(),
            sam=float(r["sam"]),
            machine_type=mt,
            skill_level=int(r.get("skill_level", 1) or 1),
            section=str(r["section"]).strip() if r.get("section") else None,
        )
        db.add(op)
        db.flush()
        op_by_code[op.op_code] = op

    for r in rows:
        preds = r.get("predecessors") or ""
        if not preds or (isinstance(preds, float) and pd.isna(preds)):
            continue
        for code in str(preds).split(","):
            code = code.strip()
            if not code:
                continue
            if code not in op_by_code:
                raise HTTPException(400, f"Predecessor {code} unknown for {r['op_code']}")
            db.add(OperationPrecedence(
                style_id=style.id,
                predecessor_id=op_by_code[code].id,
                successor_id=op_by_code[r["op_code"]].id,
            ))

    style.total_sam = sum(float(o.sam) for o in op_by_code.values())
    db.commit()
    db.refresh(style)

    precs = db.query(OperationPrecedence).filter(OperationPrecedence.style_id == style.id).all()
    return {
        "id": style.id,
        "style_code": style.style_code,
        "name": style.name,
        "garment_type": style.garment_type,
        "total_sam": float(style.total_sam) if style.total_sam else None,
        "description": style.description,
        "operations": style.operations,
        "precedence": [{"predecessor_id": p.predecessor_id, "successor_id": p.successor_id} for p in precs],
    }
