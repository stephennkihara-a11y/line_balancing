from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Operator, OperatorSkill, User, UserRole
from ..schemas.operator import OperatorCreate, OperatorUpdate, OperatorOut, SkillEntry
from ..auth.security import require_role, get_current_user

router = APIRouter(prefix="/api/operators", tags=["operators"])


def _replace_skills(db: Session, operator: Operator, skills: list[SkillEntry]) -> None:
    db.query(OperatorSkill).filter(OperatorSkill.operator_id == operator.id).delete()
    for s in skills:
        db.add(OperatorSkill(
            operator_id=operator.id,
            operation_id=s.operation_id,
            efficiency=s.efficiency,
            is_certified=s.is_certified,
        ))


@router.get("", response_model=list[OperatorOut])
def list_operators(
    line_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Operator]:
    q = db.query(Operator).options(selectinload(Operator.skills))
    if line_id is not None:
        q = q.filter(Operator.current_line_id == line_id)
    return q.order_by(Operator.employee_code).all()


@router.get("/{operator_id}", response_model=OperatorOut)
def get_operator(operator_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Operator:
    op = db.query(Operator).options(selectinload(Operator.skills)).filter(Operator.id == operator_id).first()
    if not op:
        raise HTTPException(404, "Operator not found")
    return op


@router.post("", response_model=OperatorOut, status_code=201)
def create_operator(
    payload: OperatorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.SUPERVISOR)),
) -> Operator:
    if db.query(Operator).filter(Operator.employee_code == payload.employee_code).first():
        raise HTTPException(409, "Employee code exists")
    data = payload.model_dump(exclude={"skills"})
    op = Operator(**data)
    db.add(op)
    db.flush()
    _replace_skills(db, op, payload.skills)
    db.commit()
    db.refresh(op)
    return op


@router.put("/{operator_id}", response_model=OperatorOut)
def update_operator(
    operator_id: int, payload: OperatorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.SUPERVISOR)),
) -> Operator:
    op = db.get(Operator, operator_id)
    if not op:
        raise HTTPException(404, "Operator not found")
    data = payload.model_dump(exclude_unset=True, exclude={"skills"})
    for k, v in data.items():
        setattr(op, k, v)
    if payload.skills is not None:
        _replace_skills(db, op, payload.skills)
    db.commit()
    db.refresh(op)
    return op


@router.delete("/{operator_id}", status_code=204)
def delete_operator(
    operator_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER)),
) -> None:
    op = db.get(Operator, operator_id)
    if not op:
        raise HTTPException(404, "Operator not found")
    db.delete(op)
    db.commit()
