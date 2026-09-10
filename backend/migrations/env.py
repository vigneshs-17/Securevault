"""Alembic environment; supports an injected test connection."""
from alembic import context
from sqlalchemy import create_engine, pool

from app.db.base import Base
import app.models  # noqa: F401 -- register metadata without loading runtime secrets

config = context.config
target_metadata = Base.metadata


def database_url():
    import os
    from pathlib import Path
    from dotenv import dotenv_values

    value = os.environ.get("DATABASE_URL") or dotenv_values(
        Path(__file__).resolve().parents[1] / ".env"
    ).get("DATABASE_URL")
    if not value:
        raise RuntimeError("Set DATABASE_URL or configure backend/.env before migrating.")
    return value


def migrate(connection):
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    engine = create_engine(database_url(), poolclass=pool.NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            migrate(connection)
    finally:
        engine.dispose()
