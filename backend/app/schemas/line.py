from pydantic import BaseModel, Field


class LineCreate(BaseModel):
    code: str = Field(max_length=40)
    name: str = Field(max_length=120)
    capacity: int = Field(default=30, ge=1, le=200)
    working_minutes: int = Field(default=480, ge=60, le=1440)


class LineUpdate(BaseModel):
    name: str | None = None
    capacity: int | None = None
    working_minutes: int | None = None
    is_active: bool | None = None


class LineOut(BaseModel):
    id: int
    code: str
    name: str
    capacity: int
    working_minutes: int
    is_active: bool

    class Config:
        from_attributes = True
