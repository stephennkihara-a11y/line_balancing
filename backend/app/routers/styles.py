from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Style, Operation, OperationPrecedence, User, UserRole
from ..schemas.style import (
    StyleCreate, StyleUpdate, StyleOut, StyleDetail,
    OperationCreate, OperationOut, PrecedenceCreate, PrecedenceOut,
)
from ..auth.security import require_role, get_current_user

router = APIRouter(prefix="/api/styles", tags=["styles"])


def _recalc_total_sam(db: Session, style: Style) -> None:
    total = sum(float(o.sam) for o in style.operations)
    style.total_sam = total


@router.get("", response_model=list[StyleOut])
def list_styles(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Style]:
    return db.query(Style).order_by(Style.style_code).all()


@router.get("/{style_id}", response_model=StyleDetail)
def get_style(style_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    style = db.query(Style).options(selectinload(Style.operations)).filter(Style.id == style_id).first()
    if not style:
        raise HTTPException(404, "Style not found")
    prec = (
        db.query(OperationPrecedence)
        .filter(OperationPrecedence.style_id == style_id)
        .all()
    )
    return {
        "id": style.id,
        "style_code": style.style_code,
        "name": style.name,
        "garment_type": style.garment_type,
        "total_sam": float(style.total_sam) if style.total_sam else None,
        "description": style.description,
        "operations": style.operations,
        "precedence": [{"predecessor_id": p.predecessor_id, "successor_id": p.successor_id} for p in prec],
    }


@router.post("", response_model=StyleDetail, status_code=201)
def create_style(
    payload: StyleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE)),
):
    if db.query(Style).filter(Style.style_code == payload.style_code).first():
        raise HTTPException(409, "Style code exists")
    style = Style(
        style_code=payload.style_code,
        name=payload.name,
        garment_type=payload.garment_type,
        description=payload.description,
    )
    db.add(style)
    db.flush()

    op_by_code: dict[str, Operation] = {}
    for op in payload.operations:
        o = Operation(
            style_id=style.id,
            op_code=op.op_code,
            sequence=op.sequence,
            description=op.description,
            sam=op.sam,
            machine_type=op.machine_type,
            skill_level=op.skill_level,
            section=op.section,
        )
        db.add(o)
        db.flush()
        op_by_code[op.op_code] = o

    for op in payload.operations:
        for pred_code in op.predecessor_op_codes:
            if pred_code not in op_by_code:
                raise HTTPException(400, f"Predecessor {pred_code} for {op.op_code} not in style")
            db.add(OperationPrecedence(
                style_id=style.id,
                predecessor_id=op_by_code[pred_code].id,
                successor_id=op_by_code[op.op_code].id,
            ))
    db.flush()
    db.refresh(style)
    _recalc_total_sam(db, style)
    db.commit()
    return get_style(style.id, db, _)


@router.put("/{style_id}", response_model=StyleOut)
def update_style(
    style_id: int, payload: StyleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE)),
) -> Style:
    style = db.get(Style, style_id)
    if not style:
        raise HTTPException(404, "Style not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(style, k, v)
    db.commit()
    db.refresh(style)
    return style


@router.post("/{style_id}/operations", response_model=OperationOut, status_code=201)
def add_operation(
    style_id: int, payload: OperationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE)),
) -> Operation:
    style = db.query(Style).options(selectinload(Style.operations)).filter(Style.id == style_id).first()
    if not style:
        raise HTTPException(404, "Style not found")
    if any(o.op_code == payload.op_code for o in style.operations):
        raise HTTPException(409, "op_code already exists in style")
    o = Operation(
        style_id=style_id,
        op_code=payload.op_code,
        sequence=payload.sequence,
        description=payload.description,
        sam=payload.sam,
        machine_type=payload.machine_type,
        skill_level=payload.skill_level,
        section=payload.section,
    )
    db.add(o)
    db.flush()
    for pred_code in payload.predecessor_op_codes:
        pred = next((x for x in style.operations if x.op_code == pred_code), None)
        if pred is None:
            raise HTTPException(400, f"Predecessor {pred_code} not found in style")
        db.add(OperationPrecedence(style_id=style_id, predecessor_id=pred.id, successor_id=o.id))
    db.refresh(style)
    _recalc_total_sam(db, style)
    db.commit()
    db.refresh(o)
    return o


@router.delete("/{style_id}/operations/{op_id}", status_code=204)
def delete_operation(
    style_id: int, op_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE)),
) -> None:
    op = db.query(Operation).filter(Operation.id == op_id, Operation.style_id == style_id).first()
    if not op:
        raise HTTPException(404, "Operation not found")
    db.delete(op)
    db.flush()
    style = db.get(Style, style_id)
    _recalc_total_sam(db, style)
    db.commit()


@router.post("/{style_id}/precedence", response_model=PrecedenceOut, status_code=201)
def add_precedence(
    style_id: int, payload: PrecedenceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE)),
) -> dict:
    ops = db.query(Operation).filter(Operation.style_id == style_id).all()
    by_code = {o.op_code: o for o in ops}
    if payload.predecessor_op_code not in by_code or payload.successor_op_code not in by_code:
        raise HTTPException(400, "Operation code not found in style")
    p, s = by_code[payload.predecessor_op_code], by_code[payload.successor_op_code]
    if p.id == s.id:
        raise HTTPException(400, "Self-precedence not allowed")
    db.add(OperationPrecedence(style_id=style_id, predecessor_id=p.id, successor_id=s.id))
    db.commit()
    return {"predecessor_id": p.id, "successor_id": s.id}


@router.delete("/{style_id}", status_code=204)
def delete_style(
    style_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER)),
) -> None:
    s = db.get(Style, style_id)
    if not s:
        raise HTTPException(404, "Style not found")
    db.delete(s)
    db.commit()
