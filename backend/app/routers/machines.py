from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Machine, User, UserRole
from ..schemas.machine import MachineCreate, MachineUpdate, MachineOut
from ..auth.security import require_role, get_current_user

router = APIRouter(prefix="/api/machines", tags=["machines"])


@router.get("", response_model=list[MachineOut])
def list_machines(
    line_id: int | None = None, type: str | None = None,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> list[Machine]:
    q = db.query(Machine)
    if line_id is not None:
        q = q.filter(Machine.line_id == line_id)
    if type:
        q = q.filter(Machine.type == type)
    return q.order_by(Machine.machine_code).all()


@router.post("", response_model=MachineOut, status_code=201)
def create_machine(
    payload: MachineCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.SUPERVISOR)),
) -> Machine:
    if db.query(Machine).filter(Machine.machine_code == payload.machine_code).first():
        raise HTTPException(409, "Machine code already exists")
    m = Machine(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.put("/{machine_id}", response_model=MachineOut)
def update_machine(
    machine_id: int, payload: MachineUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.SUPERVISOR)),
) -> Machine:
    m = db.get(Machine, machine_id)
    if not m:
        raise HTTPException(404, "Machine not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{machine_id}", status_code=204)
def delete_machine(
    machine_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER)),
) -> None:
    m = db.get(Machine, machine_id)
    if not m:
        raise HTTPException(404, "Machine not found")
    db.delete(m)
    db.commit()
