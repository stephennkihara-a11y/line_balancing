"""Run Alembic migrations programmatically at startup.

Replaces the previous `Base.metadata.create_all` so deployments get the
same schema definition as developers running `alembic upgrade head`.
Idempotent: if the DB is already at head, this is a no-op.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import get_settings

logger = logging.getLogger("line_balancing.migrations")


def alembic_config() -> Config:
    """Build a Config object pinned to this package's alembic.ini."""
    backend_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


def run_migrations() -> None:
    cfg = alembic_config()
    logger.info("Running alembic upgrade head…")
    command.upgrade(cfg, "head")
    logger.info("Migrations complete.")
