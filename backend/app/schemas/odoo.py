"""Pydantic schemas for the Odoo 18 integration surface.

We mirror the spirit of Odoo's external API: each endpoint takes a
`model` name + `domain` (filter) + optional `fields` and returns a list
of records. Authentication piggy-backs on our JWT but the response shape
is Odoo-friendly so a third-party Odoo connector can map it directly.
"""
from typing import Any
from pydantic import BaseModel, Field


class OdooSearchReadRequest(BaseModel):
    model: str                                  # e.g. 'mrp.routing.workcenter'
    domain: list[Any] = Field(default_factory=list)   # Odoo domain
    fields: list[str] | None = None
    limit: int = Field(default=200, ge=1, le=2000)
    offset: int = Field(default=0, ge=0)


class OdooSearchReadResponse(BaseModel):
    model: str
    length: int
    records: list[dict[str, Any]]


class OdooExternalIdMap(BaseModel):
    entity: str                                 # local entity name
    local_id: int
    erp_model: str
    erp_id: str


class OdooExternalIdOut(BaseModel):
    id: int
    entity: str
    local_id: int
    erp_system: str
    erp_model: str | None
    erp_id: str

    class Config:
        from_attributes = True
