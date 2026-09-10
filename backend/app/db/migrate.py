"""Versioned schema setup and guarded adoption of the original database."""
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, inspect
from sqlalchemy.engine import Engine

from app.db.base import Base
import app.models  # noqa: F401

BASELINE = "0001_initial_schema"


def migration_config() -> Config:
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations").replace("%", "%%"))
    return config


def upgrade_database(engine: Engine) -> None:
    with engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def adopt_existing_database(engine: Engine) -> None:
    """Stamp only a verified original schema; never silently alter legacy data."""
    config = migration_config()
    if ScriptDirectory.from_config(config).get_current_head() not in {BASELINE, "0002_vault_metadata"}:
        raise RuntimeError("Baseline adoption requires the original baseline release.")
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "alembic_version" in inspector.get_table_names():
            raise RuntimeError("Database already has migration tracking; use upgrade instead.")
        context = MigrationContext.configure(connection, opts={
            "compare_type": True, "compare_server_default": True,
        })
        baseline_metadata = MetaData()
        for model_table in Base.metadata.sorted_tables:
            table = model_table.to_metadata(baseline_metadata)
            if table.name == "vault_items":
                for name in ("item_type", "created_at", "updated_at"):
                    table._columns.remove(table.c[name])
        differences = compare_metadata(context, baseline_metadata)
        primary_keys_match = all(
            inspector.get_pk_constraint(table.name)["constrained_columns"]
            == [column.name for column in table.primary_key]
            for table in Base.metadata.sorted_tables
            if inspector.has_table(table.name)
        )
        if differences or not primary_keys_match:
            raise RuntimeError("Existing schema differs from the baseline; adoption refused. Review schema before migrating.")
        config.attributes["connection"] = connection
        command.stamp(config, BASELINE)


def main():
    import argparse
    from app.db.database import engine

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["upgrade", "adopt-existing"])
    args = parser.parse_args()
    try:
        if args.action == "adopt-existing":
            adopt_existing_database(engine)
        else:
            upgrade_database(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
