from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Line, User, UserRole
from ..schemas.line import LineCreate, LineUpdate, LineOut
from ..auth.security import require_role, get_current_user

router = APIRouter(prefix="/api/lines", tags=["lines"])


@router.get("", response_model=list[LineOut])
def list_lines(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Line]:
    return db.query(Line).order_by(Line.code).all()


@router.post("", response_model=LineOut, status_code=201)
def create_line(
    payload: LineCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE)),
) -> Line:
    if db.query(Line).filter(Line.code == payload.code).first():
        raise HTTPException(409, "Line code already exists")
    line = Line(**payload.model_dump())
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.put("/{line_id}", response_model=LineOut)
def update_line(
    line_id: int, payload: LineUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE)),
) -> Line:
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "Line not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(line, k, v)
    db.commit()
    db.refresh(line)
    return line


@router.delete("/{line_id}", status_code=204)
def delete_line(
    line_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER)),
) -> None:
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "Line not found")
    db.delete(line)
    db.commit()
