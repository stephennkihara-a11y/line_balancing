"""machines.last_maintenance_at

Revision ID: 0002_machine_maintenance
Revises: 0001_initial
Create Date: 2026-05-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_machine_maintenance"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("machines") as batch:
        batch.add_column(
            sa.Column("last_maintenance_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("machines") as batch:
        batch.drop_column("last_maintenance_at")
